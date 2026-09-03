
import json
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (
    RegisterForm, StudentProfileForm, LandlordProfileForm,
    StudentAgentProfileForm, ListingForm, AgentVerificationForm,
    LoginForm, SearchForm,
)
from .models import (
    User, StudentProfile, AgentProfile, LandlordProfile,
    StudentAgentProfile, Listing, ListingMedia, SavedListing,
    Payment, VerificationRequest,
)
from .paystack_utils import verify_transaction, PaystackError


# ───────────────────────── Landing & Public ─────────────────────────

def get_available_schools():
    """
    Real, distinct school names pulled from live listings -- not a
    hardcoded list, so it always reflects what's actually searchable
    right now and grows automatically as new listings go live.
    """
    return (
        Listing.objects
        .filter(status="live")
        .exclude(school_name="")
        .exclude(school_name__isnull=True)
        .values_list("school_name", flat=True)
        .distinct()
        .order_by("school_name")
    )


def landing(request):
    top_agents = (
        User.objects
        .filter(role__in=["agent", "student_agent"], is_verified=True)
        .annotate(listing_count=Count("listings", filter=Q(listings__status="live")))
        .filter(listing_count__gt=0)
        .order_by("-listing_count")[:3]
    )
    featured_listings = (
        Listing.objects
        .filter(status="live", is_featured=True)
        .order_by("-updated_at")[:6]
    )
    return render(request, "uninest/landing.html", {
        "top_agents": top_agents,
        "available_schools": get_available_schools(),
        "featured_listings": featured_listings,
    })


def search_listings(request):
    form = SearchForm(request.GET or None)
    listings = Listing.objects.filter(status="live")
    if form.is_valid():
        school = form.cleaned_data["school_name"]
        location = form.cleaned_data["location"]
        listings = listings.filter(
            Q(school_name__icontains=school) | Q(general_location__icontains=school),
            general_location__icontains=location,
        )
    return render(request, "uninest/search_results.html", {
        "form": form,
        "listings": listings,
        "query": request.GET,
        "available_schools": get_available_schools(),
    })


def listing_detail(request, pk):
    listing = get_object_or_404(Listing, pk=pk, status="live")
    unlocked = False
    if request.user.is_authenticated and request.user.has_active_subscription():
        unlocked = True
    visit_message = (
        f"Hi {listing.landlord_name}, I found your listing at {listing.general_location} "
        f"on UNINEST and would like to book a visit. When works for you?"
    )
    return render(request, "uninest/listing_detail.html", {
        "listing": listing,
        "unlocked": unlocked,
        "visit_message": visit_message,
    })


# ───────────────────────── Auth ─────────────────────────

def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            role = user.role
            if role == "student":
                StudentProfile.objects.create(user=user, school_name="", department="")
            elif role == "agent":
                AgentProfile.objects.create(user=user)
            elif role == "landlord":
                LandlordProfile.objects.create(user=user)
            # student_agent profile created in complete_profile
            login(request, user)
            messages.success(request, "Account created! Complete your profile.")
            return redirect("complete_profile")
    else:
        form = RegisterForm()
    return render(request, "uninest/register.html", {"form": form})


class CustomLoginView(LoginView):
    template_name = "uninest/login.html"
    authentication_form = LoginForm

    def get_success_url(self):
        if self.request.user.is_staff:
            return reverse("admin_dashboard")
        return reverse("dashboard")


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("landing")


@login_required
def complete_profile(request):
    user = request.user
    role = user.role

    if role == "student":
        profile, _ = StudentProfile.objects.get_or_create(
            user=user, defaults={"school_name": "", "department": ""}
        )
        form_class = StudentProfileForm
        instance = profile
    elif role == "landlord":
        profile, _ = LandlordProfile.objects.get_or_create(user=user)
        form_class = LandlordProfileForm
        instance = profile
    elif role == "student_agent":
        try:
            instance = user.student_agent_profile
        except StudentAgentProfile.DoesNotExist:
            instance = None
        form_class = StudentAgentProfileForm
    else:  # agent
        messages.success(request, "Welcome! You can start posting adverts.")
        return redirect("dashboard")

    if request.method == "POST":
        form = form_class(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            obj = form.save(commit=False)
            if role == "student_agent" and instance is None:
                obj.user = user
            obj.save()
            if role == "student_agent":
                user.verification_pending = True
                user.save()
                VerificationRequest.objects.create(user=user, request_type="student_agent")
                messages.info(request, "Registration successful — awaiting school verification.")
            elif role == "landlord":
                data = form.cleaned_data
                if data.get("location_of_house"):
                    listing = Listing.objects.create(
                        owner=user,
                        general_location=data["location_of_house"],
                        full_address=data.get("full_address", data["location_of_house"]),
                        landlord_name=user.get_full_name(),
                        landlord_phone=user.phone,
                        rent_amount=data.get("price_per_room", 0),
                        number_of_rooms=data.get("number_of_rooms", 1),
                        status="pending",
                    )
                    for f in request.FILES.getlist("photos"):
                        ListingMedia.objects.create(listing=listing, file=f, media_type="photo")
                VerificationRequest.objects.create(user=user, request_type="landlord")
                messages.success(request, "Profile complete. Ownership docs submitted for review.")
            else:
                messages.success(request, "Profile complete!")
            return redirect("dashboard")
    else:
        form = form_class(instance=instance)

    return render(request, "uninest/complete_profile.html", {
        "form": form,
        "role": role,
    })


# ───────────────────────── Dashboard router ─────────────────────────

@login_required
def dashboard(request):
    role = request.user.role
    if role == "student":
        return student_dashboard(request)
    if role == "agent":
        return agent_dashboard(request)
    if role == "landlord":
        return landlord_dashboard(request)
    if role == "student_agent":
        return student_agent_dashboard(request)
    if request.user.is_staff:
        return redirect("admin_dashboard")
    messages.warning(request, "Role not set. Please complete registration.")
    return redirect("complete_profile")


@login_required
def student_dashboard(request):
    user = request.user
    saved = SavedListing.objects.filter(student=user).select_related("listing")
    payments = Payment.objects.filter(user=user).order_by("-created_at")[:10]
    return render(request, "uninest/dashboards/student.html", {
        "saved": saved,
        "payments": payments,
        "has_sub": user.has_active_subscription(),
    })


@login_required
def agent_dashboard(request):
    user = request.user
    listings = Listing.objects.filter(owner=user)
    return render(request, "uninest/dashboards/agent.html", {
        "listings": listings,
        "is_verified": user.is_verified,
        "verification_pending": user.verification_pending,
    })


@login_required
def landlord_dashboard(request):
    user = request.user
    listings = Listing.objects.filter(owner=user)
    interested = SavedListing.objects.filter(
        listing__owner=user
    ).select_related("student", "listing")
    payments = Payment.objects.filter(user=user).order_by("-created_at")[:5]
    return render(request, "uninest/dashboards/landlord.html", {
        "listings": listings,
        "interested": interested,
        "payments": payments,
    })


@login_required
def student_agent_dashboard(request):
    user = request.user
    profile = getattr(user, "student_agent_profile", None)
    verified = profile.school_verified if profile else False

    listings = Listing.objects.filter(owner=user).order_by("-created_at")
    interested = (
        SavedListing.objects
        .filter(listing__owner=user)
        .select_related("student", "listing")
        .order_by("-saved_at")[:10]
    )

    return render(request, "uninest/dashboards/student_agent.html", {
        "profile": profile,
        "verified": verified,
        "listings": listings,
        "interested": interested,
        "interested_count": SavedListing.objects.filter(listing__owner=user).count(),
    })


# ───────────────────────── Agent / Landlord actions ─────────────────────────

@login_required
def create_listing(request):
    if request.user.role not in ("agent", "landlord", "student_agent"):
        messages.error(request, "Only agents, landlords, and student agents can post listings.")
        return redirect("dashboard")
    if request.method == "POST":
        form = ListingForm(request.POST, request.FILES)
        if form.is_valid():
            listing = form.save(commit=False)
            listing.owner = request.user
            listing.is_verified_agent = request.user.is_verified
            listing.status = "pending"
            listing.save()
            for f in request.FILES.getlist("photos"):
                ListingMedia.objects.create(listing=listing, file=f, media_type="photo")
            for f in request.FILES.getlist("videos"):
                ListingMedia.objects.create(listing=listing, file=f, media_type="video")
            messages.success(request, "Listing submitted for review.")
            return redirect("dashboard")
    else:
        form = ListingForm()
    return render(request, "uninest/create_listing.html", {"form": form})


@login_required
def agent_get_verified(request):
    if request.user.role != "agent":
        return redirect("dashboard")
    if request.method == "POST":
        form = AgentVerificationForm(request.POST)
        if form.is_valid():
            profile, _ = AgentProfile.objects.get_or_create(user=request.user)
            profile.nin_number = form.cleaned_data["nin_number"]
            profile.houses_listed_count = form.cleaned_data["number_of_houses"]
            profile.verification_notes = form.cleaned_data["landlord_details"]
            profile.save()
            request.user.verification_pending = True
            request.user.save()
            VerificationRequest.objects.create(user=request.user, request_type="agent")
            messages.info(request, "Verification submitted. Awaiting approval.")
            return redirect("dashboard")
    else:
        form = AgentVerificationForm()
    return render(request, "uninest/agent_verify.html", {"form": form})


# ───────────────────────── Student actions ─────────────────────────

@login_required
def save_listing(request, pk):
    if request.user.role != "student":
        messages.error(request, "Only students can save listings.")
        return redirect("listing_detail", pk=pk)
    listing = get_object_or_404(Listing, pk=pk, status="live")
    SavedListing.objects.get_or_create(student=request.user, listing=listing)
    messages.success(request, "Listing saved.")
    return redirect("listing_detail", pk=pk)


@login_required
def unsave_listing(request, pk):
    SavedListing.objects.filter(student=request.user, listing_id=pk).delete()
    messages.info(request, "Removed from saved.")
    return redirect("dashboard")


# ───────────────────────── Paystack Subscription (Nigeria) ─────────────────────────

@login_required
def subscribe(request):
    """
    Renders the subscribe page. A fresh, unique reference is generated
    server-side on every visit so the JS SDK never has to invent one --
    this is what verify_payment() will check.
    """
    user = request.user
    if user.has_active_subscription():
        messages.info(request, "You already have an active subscription.")
        return redirect("dashboard")

    payment = Payment.objects.create(
        user=user,
        amount=settings.UNINEST_SUBSCRIPTION_AMOUNT,
        currency="ngn",
        payment_type="subscription",
        status="pending",
        paystack_reference=str(uuid.uuid4()),
    )

    context = {
        "paystack_public_key": settings.PAYSTACK_PUBLIC_KEY,
        "amount": settings.UNINEST_SUBSCRIPTION_AMOUNT,
        "amount_kobo": int(settings.UNINEST_SUBSCRIPTION_AMOUNT) * 100,
        "reference": payment.paystack_reference,
        "customer_email": user.email,
        "customer_name": user.get_full_name() or user.username,
    }
    return render(request, "uninest/Subscribe.html", context)


# ───────────────────────── Paystack Rent Payment ─────────────────────────

@login_required
def pay_rent(request, pk):
    """
    Renders the rent checkout page for one specific listing. Only makes
    sense once the listing is unlocked -- paying rent on an address you
    can't even see yet isn't a real flow.
    """
    listing = get_object_or_404(Listing, pk=pk, status="live")

    if not request.user.has_active_subscription():
        messages.warning(request, "Unlock this listing first before paying rent.")
        return redirect("listing_detail", pk=pk)

    payment = Payment.objects.create(
        user=request.user,
        listing=listing,
        amount=listing.rent_amount,
        currency="ngn",
        payment_type="rent",
        status="pending",
        paystack_reference=str(uuid.uuid4()),
    )

    context = {
        "paystack_public_key": settings.PAYSTACK_PUBLIC_KEY,
        "amount": listing.rent_amount,
        "amount_kobo": int(listing.rent_amount) * 100,
        "reference": payment.paystack_reference,
        "customer_email": request.user.email,
        "customer_name": request.user.get_full_name() or request.user.username,
        "listing": listing,
    }
    return render(request, "uninest/pay_rent.html", context)


@login_required
@require_POST
def verify_payment(request):
    """
    Called by the Paystack popup's callback() after checkout completes,
    for BOTH subscription unlocks and rent payments. We ignore whatever
    the browser claims and re-check the real status with Paystack's API
    before activating anything -- then branch on payment_type, since a
    rent payment should never touch subscription fields and vice versa.
    """
    try:
        body = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Bad request body"}, status=400)

    reference = body.get("reference")
    if not reference:
        return JsonResponse({"ok": False, "error": "Missing reference"}, status=400)

    try:
        payment = Payment.objects.get(paystack_reference=reference, user=request.user)
    except Payment.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Unknown payment reference"}, status=404)

    if payment.status == "succeeded":
        return JsonResponse({"ok": True, "already_verified": True})

    try:
        result = verify_transaction(reference)
    except PaystackError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=502)

    if result.get("status") != "success":
        payment.status = "failed"
        payment.save()
        return JsonResponse(
            {"ok": False, "error": "Payment not confirmed", "status": result.get("status")},
            status=402,
        )

    payment.status = "succeeded"
    payment.save()

    if payment.payment_type == "subscription":
        user = request.user
        base = user.subscription_end if user.has_active_subscription() else timezone.now()
        user.subscription_end = base + timedelta(days=30)
        user.subscription_active = True
        user.save(update_fields=["subscription_end", "subscription_active"])
        messages.success(request, "Payment successful! Full listing details unlocked for 30 days.")
        return JsonResponse({"ok": True, "active_until": user.subscription_end.isoformat()})

    if payment.payment_type == "rent":
        messages.success(
            request,
            f"Rent payment of ₦{payment.amount:,.0f} confirmed for {payment.listing.general_location}."
        )
        # NOTE: this collects the payment into UNINEST's own Paystack account.
        # Actually forwarding funds to the landlord requires Paystack Subaccounts
        # or the Transfers API -- that's a separate integration, not automatic.
        return JsonResponse({"ok": True, "listing_id": payment.listing_id})

    return JsonResponse({"ok": True})


# ───────────────────────── Profile photo ─────────────────────────

@login_required
@require_POST
def update_profile_photo(request):
    photo = request.FILES.get("profile_photo")
    if photo:
        request.user.profile_photo = photo
        request.user.save(update_fields=["profile_photo"])
        messages.success(request, "Profile photo updated.")
    return redirect("dashboard")


# ───────────────────────── Receipts ─────────────────────────

@login_required
def download_receipt(request, pk):
    """
    Streams a PDF receipt for one payment. The payment's own user can
    always download it; staff can download any payment's receipt (for
    support/reporting). Only succeeded payments have a receipt to issue.
    """
    from django.http import HttpResponse, Http404
    from .receipts import build_receipt_pdf

    if request.user.is_staff:
        payment = get_object_or_404(Payment, pk=pk)
    else:
        payment = get_object_or_404(Payment, pk=pk, user=request.user)

    if payment.status != "succeeded":
        raise Http404("No receipt available for this payment.")

    pdf_bytes = build_receipt_pdf(payment)

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="uninest-receipt-UN-{payment.pk:06d}.pdf"'
    return response


# ───────────────────────── Staff Admin Dashboard ─────────────────────────

def staff_required(view_func):
    """
    Same idea as @login_required but also checks is_staff, and redirects
    to the normal site login (not /admin/login/) so it matches the rest
    of UNINEST's auth flow.
    """
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            messages.error(request, "You don't have access to that page.")
            return redirect("dashboard")
        return view_func(request, *args, **kwargs)
    return wrapper


@staff_required
def admin_dashboard(request):
    import json
    from datetime import timedelta
    from django.db.models import Sum
    from django.db.models.functions import TruncMonth
    from django.utils import timezone

    # ── Reports ──
    revenue_by_type = (
        Payment.objects.filter(status="succeeded")
        .values("payment_type")
        .annotate(total=Sum("amount"), count=Count("id"))
    )
    total_revenue = Payment.objects.filter(status="succeeded").aggregate(total=Sum("amount"))["total"] or 0

    users_by_role = User.objects.values("role").annotate(count=Count("id")).order_by("role")
    listings_by_status = Listing.objects.values("status").annotate(count=Count("id")).order_by("status")

    recent_payments = Payment.objects.select_related("user", "listing").order_by("-created_at")[:10]

    # ── Verifications ──
    pending_verifications = (
        VerificationRequest.objects
        .filter(status="pending")
        .select_related("user")
        .order_by("submitted_at")
    )

    # ── Listings needing moderation ──
    pending_listings = (
        Listing.objects
        .filter(status="pending")
        .select_related("owner")
        .order_by("-created_at")[:10]
    )

    # ── Live listings, for featuring/unfeaturing ──
    live_listings_for_featuring = (
        Listing.objects
        .filter(status="live")
        .select_related("owner")
        .order_by("-is_featured", "-created_at")[:20]
    )

    # ── Recently joined users ──
    recent_users = User.objects.order_by("-date_joined")[:10]

    # ── Monthly revenue, last 6 months (for the bar chart) ──
    six_months_ago = timezone.now() - timedelta(days=180)
    monthly_revenue_qs = (
        Payment.objects.filter(status="succeeded", created_at__gte=six_months_ago)
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(total=Sum("amount"))
        .order_by("month")
    )
    monthly_revenue_labels = [row["month"].strftime("%b") for row in monthly_revenue_qs]
    monthly_revenue_values = [float(row["total"]) for row in monthly_revenue_qs]

    # ── Monthly new listings, last 6 months (for the area chart) ──
    monthly_listings_qs = (
        Listing.objects.filter(created_at__gte=six_months_ago)
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )
    monthly_listings_labels = [row["month"].strftime("%b") for row in monthly_listings_qs]
    monthly_listings_values = [row["count"] for row in monthly_listings_qs]

    # ── Verification approval rate (real, from actual decided requests) ──
    decided = VerificationRequest.objects.exclude(status="pending")
    decided_count = decided.count()
    approved_count = decided.filter(status="approved").count()
    approval_rate = round((approved_count / decided_count) * 100, 1) if decided_count else 0
    rejection_rate = round(100 - approval_rate, 1) if decided_count else 0

    context = {
        "total_revenue": total_revenue,
        "revenue_by_type": revenue_by_type,
        "users_by_role": users_by_role,
        "listings_by_status": listings_by_status,
        "recent_payments": recent_payments,
        "pending_verifications": pending_verifications,
        "pending_count": pending_verifications.count(),
        "pending_listings": pending_listings,
        "live_listings_for_featuring": live_listings_for_featuring,
        "recent_users": recent_users,
        "total_users": User.objects.count(),
        "total_listings": Listing.objects.count(),
        "live_listings": Listing.objects.filter(status="live").count(),
        "approval_rate": approval_rate,
        "decided_count": decided_count,
        "monthly_revenue_labels": json.dumps(monthly_revenue_labels),
        "monthly_revenue_values": json.dumps(monthly_revenue_values),
        "monthly_listings_labels": json.dumps(monthly_listings_labels),
        "monthly_listings_values": json.dumps(monthly_listings_values),
    }
    return render(request, "uninest/admin_dashboard.html", context)


@staff_required
@require_POST
def approve_verification(request, pk):
    vr = get_object_or_404(VerificationRequest, pk=pk, status="pending")
    vr.status = "approved"
    vr.reviewed_at = timezone.now()
    vr.save()

    user = vr.user
    user.is_verified = True
    user.verification_pending = False
    user.save()

    if vr.request_type == "student_agent":
        try:
            user.student_agent_profile.school_verified = True
            user.student_agent_profile.save()
        except Exception:
            pass
    if vr.request_type == "agent":
        Listing.objects.filter(owner=user).update(is_verified_agent=True)

    messages.success(request, f"{user.get_full_name() or user.username} approved.")
    return redirect("admin_dashboard")


@staff_required
@require_POST
def reject_verification(request, pk):
    vr = get_object_or_404(VerificationRequest, pk=pk, status="pending")
    vr.status = "rejected"
    vr.reviewed_at = timezone.now()
    vr.notes = request.POST.get("notes", "")
    vr.save()

    vr.user.verification_pending = False
    vr.user.save()

    messages.info(request, f"{vr.user.get_full_name() or vr.user.username}'s request was rejected.")
    return redirect("admin_dashboard")


@staff_required
@require_POST
def approve_listing(request, pk):
    listing = get_object_or_404(Listing, pk=pk)
    listing.status = "live"
    listing.save(update_fields=["status"])
    messages.success(request, f"Listing '{listing.general_location}' is now live.")
    return redirect("admin_dashboard")


@staff_required
@require_POST
def archive_listing(request, pk):
    listing = get_object_or_404(Listing, pk=pk)
    listing.status = "archived"
    listing.save(update_fields=["status"])
    messages.info(request, f"Listing '{listing.general_location}' archived.")
    return redirect("admin_dashboard")


@staff_required
@require_POST
def toggle_featured_listing(request, pk):
    listing = get_object_or_404(Listing, pk=pk, status="live")
    listing.is_featured = not listing.is_featured
    listing.save(update_fields=["is_featured"])

    state = "featured" if listing.is_featured else "unfeatured"
    messages.success(request, f"'{listing.general_location}' {state} on the landing page.")
    return redirect("admin_dashboard")


@staff_required
@require_POST
def toggle_user_active(request, pk):
    target = get_object_or_404(User, pk=pk)

    if target.pk == request.user.pk:
        messages.error(request, "You can't suspend your own account.")
        return redirect("admin_dashboard")
    if target.is_superuser:
        messages.error(request, "Superuser accounts can't be suspended from here.")
        return redirect("admin_dashboard")

    target.is_active = not target.is_active
    target.save(update_fields=["is_active"])

    state = "reactivated" if target.is_active else "suspended"
    messages.success(request, f"{target.get_full_name() or target.username} {state}.")
    return redirect("admin_dashboard")


@staff_required
def export_payments_csv(request):
    import csv
    from django.http import HttpResponse

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="uninest-payments.csv"'

    writer = csv.writer(response)
    writer.writerow(["Date", "User", "Email", "Type", "Listing", "Amount (NGN)", "Status", "Reference"])

    payments = Payment.objects.select_related("user", "listing").order_by("-created_at")
    for p in payments:
        writer.writerow([
            p.created_at.strftime("%Y-%m-%d %H:%M"),
            p.user.get_full_name() or p.user.username,
            p.user.email,
            p.get_payment_type_display(),
            p.listing.general_location if p.listing else "",
            p.amount,
            p.status,
            p.paystack_reference or "",
        ])

    return response
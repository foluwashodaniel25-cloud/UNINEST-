from django.shortcuts import render

# Create your views here.
import stripe
from datetime import timedelta
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
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

stripe.api_key = settings.STRIPE_SECRET_KEY


# ───────────────────────── Landing & Public ─────────────────────────

def landing(request):
    return render(request, "uninest/landing.html")


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
    })


def listing_detail(request, pk):
    listing = get_object_or_404(Listing, pk=pk, status="live")
    unlocked = False
    if request.user.is_authenticated and request.user.has_active_subscription():
        unlocked = True
    return render(request, "uninest/listing_detail.html", {
        "listing": listing,
        "unlocked": unlocked,
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
    if not verified:
        return render(request, "uninest/dashboards/student_agent_pending.html")
    return render(request, "uninest/dashboards/student_agent.html", {
        "profile": profile,
    })


# ───────────────────────── Agent / Landlord actions ─────────────────────────

@login_required
def create_listing(request):
    if request.user.role not in ("agent", "landlord"):
        messages.error(request, "Only agents and landlords can post listings.")
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


# ───────────────────────── Stripe Subscription ─────────────────────────

@login_required
def create_checkout_session(request):
    """Start Stripe Checkout for ₦1,000/month (platform-wide unlock)."""
    user = request.user
    if user.has_active_subscription():
        messages.info(request, "You already have an active subscription.")
        return redirect("dashboard")

    if not user.stripe_customer_id:
        customer = stripe.Customer.create(
            email=user.email,
            name=user.get_full_name() or user.username,
            metadata={"user_id": user.id},
        )
        user.stripe_customer_id = customer.id
        user.save(update_fields=["stripe_customer_id"])

    line_items = []
    mode = "subscription"
    if settings.STRIPE_PRICE_ID:
        line_items = [{"price": settings.STRIPE_PRICE_ID, "quantity": 1}]
    else:
        mode = "payment"
        line_items = [{
            "price_data": {
                "currency": "ngn",
                "unit_amount": settings.SUBSCRIPTION_AMOUNT_NGN * 100,
                "product_data": {
                    "name": "UNINEST Monthly Access",
                    "description": "Unlock full house addresses & contact details for 30 days",
                },
            },
            "quantity": 1,
        }]

    try:
        session = stripe.checkout.Session.create(
            customer=user.stripe_customer_id,
            payment_method_types=["card"],
            line_items=line_items,
            mode=mode,
            success_url=request.build_absolute_uri(reverse("payment_success"))
                        + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=request.build_absolute_uri(reverse("payment_cancel")),
            metadata={"user_id": str(user.id)},
        )
        Payment.objects.create(
            user=user,
            amount=settings.SUBSCRIPTION_AMOUNT_NGN,
            payment_type="subscription",
            status="pending",
            stripe_session_id=session.id,
        )
        return redirect(session.url, code=303)
    except stripe.error.StripeError as e:
        messages.error(request, f"Payment error: {str(e)}")
        return redirect("dashboard")


@login_required
def payment_success(request):
    session_id = request.GET.get("session_id")
    if session_id:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            if session.payment_status == "paid":
                user = request.user
                user.subscription_active = True
                user.subscription_end = timezone.now() + timedelta(days=30)
                user.save(update_fields=["subscription_active", "subscription_end"])
                Payment.objects.filter(stripe_session_id=session_id).update(status="succeeded")
                messages.success(
                    request,
                    "Payment successful! Full listing details unlocked for 30 days."
                )
        except stripe.error.StripeError:
            messages.warning(request, "Could not verify payment. Contact support if charged.")
    return redirect("dashboard")


@login_required
def payment_cancel(request):
    messages.info(request, "Payment cancelled.")
    return redirect("dashboard")


@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        return HttpResponse(status=400)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session.get("metadata", {}).get("user_id")
        if user_id:
            try:
                user = User.objects.get(pk=user_id)
                user.subscription_active = True
                user.subscription_end = timezone.now() + timedelta(days=30)
                user.save(update_fields=["subscription_active", "subscription_end"])
                Payment.objects.filter(
                    stripe_session_id=session["id"]
                ).update(status="succeeded")
            except User.DoesNotExist:
                pass
    return HttpResponse(status=200)


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
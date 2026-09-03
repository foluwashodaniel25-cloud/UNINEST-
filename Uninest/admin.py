from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils import timezone
from .models import (
    User, StudentProfile, AgentProfile, LandlordProfile,
    StudentAgentProfile, Listing, ListingMedia, SavedListing,
    Payment, VerificationRequest, EmailVerificationCode,
)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("paystack_reference", "user", "amount", "status", "created_at")
    list_filter = ("status", "payment_type")
    search_fields = (
        "paystack_reference", "user__username", "user__email",
        "stripe_session_id",
    )


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "username", "email", "role", "is_verified",
        "subscription_active", "is_staff",
    )
    list_filter = ("role", "is_verified", "subscription_active")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("UNINEST", {
            "fields": (
                "role", "phone", "profile_photo", "is_verified",
                "verification_pending", "stripe_customer_id",
                "subscription_active", "subscription_end",
            )
        }),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("UNINEST", {"fields": ("role", "phone")}),
    )


class ListingMediaInline(admin.TabularInline):
    model = ListingMedia
    extra = 1


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = (
        "general_location", "owner", "rent_amount",
        "status", "is_verified_agent", "is_featured", "created_at",
    )
    list_filter = ("status", "rent_basis", "is_verified_agent", "is_featured")
    search_fields = (
        "general_location", "school_name",
        "full_address", "landlord_name",
    )
    inlines = [ListingMediaInline]
    actions = ["make_live", "archive"]

    @admin.action(description="Mark selected as Live")
    def make_live(self, request, queryset):
        queryset.update(status="live")

    @admin.action(description="Archive selected")
    def archive(self, request, queryset):
        queryset.update(status="archived")


@admin.register(VerificationRequest)
class VerificationRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "request_type", "status", "submitted_at")
    list_filter = ("request_type", "status")
    actions = ["approve", "reject"]

    @admin.action(description="Approve selected")
    def approve(self, request, queryset):
        for vr in queryset:
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

    @admin.action(description="Reject selected")
    def reject(self, request, queryset):
        queryset.update(status="rejected", reviewed_at=timezone.now())
        for vr in queryset:
            vr.user.verification_pending = False
            vr.user.save()


admin.site.register(StudentProfile)
admin.site.register(AgentProfile)
admin.site.register(LandlordProfile)
admin.site.register(StudentAgentProfile)
admin.site.register(ListingMedia)
admin.site.register(SavedListing)


@admin.register(EmailVerificationCode)
class EmailVerificationCodeAdmin(admin.ModelAdmin):
    list_display = ("user", "code", "used", "created_at")
    list_filter = ("used",)
    search_fields = ("user__username", "user__email", "code")
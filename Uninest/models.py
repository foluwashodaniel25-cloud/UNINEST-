from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


class User(AbstractUser):
    """Custom user with role support."""
    ROLE_CHOICES = [
        ("student", "Student"),
        ("agent", "Agent"),
        ("landlord", "Landlord"),
        ("student_agent", "Student Agent"),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    profile_photo = models.ImageField(upload_to="profiles/", blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    verification_pending = models.BooleanField(default=False)

    # Stripe
    stripe_customer_id = models.CharField(max_length=100, blank=True)
    subscription_active = models.BooleanField(default=False)
    subscription_end = models.DateTimeField(null=True, blank=True)

    def has_active_subscription(self):
        if self.subscription_active and self.subscription_end:
            return self.subscription_end > timezone.now()
        return False

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.role})"


class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="student_profile")
    school_name = models.CharField(max_length=200)
    department = models.CharField(max_length=150)
    student_id_doc = models.FileField(upload_to="verification/student_ids/", blank=True, null=True)
    nin_doc = models.FileField(upload_to="verification/nins/", blank=True, null=True)

    def __str__(self):
        return f"Student: {self.user.get_full_name()}"


class AgentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="agent_profile")
    nin_number = models.CharField(max_length=20, blank=True)
    houses_listed_count = models.PositiveIntegerField(default=0)
    verification_notes = models.TextField(blank=True)

    def __str__(self):
        return f"Agent: {self.user.get_full_name()}"


class LandlordProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="landlord_profile")
    proof_of_ownership = models.FileField(upload_to="verification/ownership/", blank=True, null=True)

    def __str__(self):
        return f"Landlord: {self.user.get_full_name()}"


class StudentAgentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="student_agent_profile")
    student_id_doc = models.FileField(upload_to="verification/student_ids/", blank=True, null=True)
    department = models.CharField(max_length=150)
    course_rep_name = models.CharField(max_length=150)
    school_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"Student Agent: {self.user.get_full_name()}"


class Listing(models.Model):
    RENT_BASIS = [
        ("monthly", "Monthly"),
        ("yearly", "Yearly"),
    ]
    STATUS = [
        ("draft", "Draft"),
        ("pending", "Pending Review"),
        ("live", "Live"),
        ("archived", "Archived"),
    ]

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="listings")
    title = models.CharField(max_length=200, blank=True)
    general_location = models.CharField(max_length=200, help_text="Area / neighborhood (public)")
    school_name = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    rent_basis = models.CharField(max_length=10, choices=RENT_BASIS, default="yearly")
    rent_amount = models.DecimalField(max_digits=12, decimal_places=2)
    agent_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    subsequent_rent = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    max_tenants = models.PositiveIntegerField(default=1)
    number_of_rooms = models.PositiveIntegerField(default=1)

    # Gated (unlocked by subscription)
    full_address = models.CharField(max_length=300)
    landlord_name = models.CharField(max_length=150)
    landlord_phone = models.CharField(max_length=20)
    agent_phone = models.CharField(max_length=20, blank=True)

    status = models.CharField(max_length=20, choices=STATUS, default="pending")
    is_verified_agent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.general_location} – ₦{self.rent_amount} ({self.get_rent_basis_display()})"

    @property
    def primary_image(self):
        media = self.media.filter(media_type="photo").first()
        return media.file.url if media else None


class ListingMedia(models.Model):
    MEDIA_TYPES = [
        ("photo", "Photo"),
        ("video", "Video"),
    ]
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="media")
    file = models.FileField(upload_to="listings/")
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPES, default="photo")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.media_type} for {self.listing_id}"


class SavedListing(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="saved_listings")
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="saves")
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("student", "listing")

    def __str__(self):
        return f"{self.student} saved {self.listing}"


class Payment(models.Model):
    PAYMENT_TYPES = [
        ("subscription", "Subscription"),
        ("other", "Other"),
    ]
    STATUS = [
        ("pending", "Pending"),
        ("succeeded", "Succeeded"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default="ngn")
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES, default="subscription")
    status = models.CharField(max_length=20, choices=STATUS, default="pending")
    stripe_session_id = models.CharField(max_length=200, blank=True)
    stripe_payment_intent = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} – ₦{self.amount} ({self.status})"


class VerificationRequest(models.Model):
    REQUEST_TYPES = [
        ("agent", "Agent Verification"),
        ("landlord", "Landlord Ownership"),
        ("student_agent", "Student Agent School"),
        ("student", "Student ID"),
    ]
    STATUS = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="verification_requests")
    request_type = models.CharField(max_length=20, choices=REQUEST_TYPES)
    status = models.CharField(max_length=20, choices=STATUS, default="pending")
    notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.request_type} – {self.user} ({self.status})"
from django.conf import settings

def stripe_keys(request):
    return {
        "STRIPE_PUBLIC_KEY": settings.STRIPE_PUBLIC_KEY,
    }
"""
Add this function to your existing Uninest/context_processors.py
(the same file that already has stripe_keys).

Then register it in settings.py's TEMPLATES -> OPTIONS -> context_processors,
alongside 'Uninest.context_processors.stripe_keys':

    'Uninest.context_processors.staff_pending_counts',
"""


def staff_pending_counts(request):
    """
    Only queries the database for staff users -- everyone else gets an
    empty dict back immediately, so this adds no overhead for regular
    students/agents/landlords browsing the site.
    """
    if not (request.user.is_authenticated and request.user.is_staff):
        return {}

    from .models import VerificationRequest, Listing

    pending_verifications = VerificationRequest.objects.filter(status="pending").count()
    pending_listings = Listing.objects.filter(status="pending").count()

    return {
        "staff_pending_total": pending_verifications + pending_listings,
    }
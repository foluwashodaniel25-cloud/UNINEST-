from django.conf import settings

def stripe_keys(request):
    return {
        "STRIPE_PUBLIC_KEY": settings.STRIPE_PUBLIC_KEY,
    }
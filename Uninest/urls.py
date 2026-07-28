from django.urls import path
from . import views
from .views import CustomLoginView

urlpatterns = [
    path("", views.landing, name="landing"),
    path("search/", views.search_listings, name="search"),
    path("listing/<int:pk>/", views.listing_detail, name="listing_detail"),

    path("register/", views.register, name="register"),
    path("login/", CustomLoginView.as_view(), name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("complete-profile/", views.complete_profile, name="complete_profile"),

    path("dashboard/", views.dashboard, name="dashboard"),
    path("listing/new/", views.create_listing, name="create_listing"),
    path("agent/verify/", views.agent_get_verified, name="agent_verify"),
    path("listing/<int:pk>/save/", views.save_listing, name="save_listing"),
    path("listing/<int:pk>/unsave/", views.unsave_listing, name="unsave_listing"),

    path("subscribe/", views.create_checkout_session, name="subscribe"),
    path("payment/success/", views.payment_success, name="payment_success"),
    path("payment/cancel/", views.payment_cancel, name="payment_cancel"),
    path("stripe/webhook/", views.stripe_webhook, name="stripe_webhook"),

    path("profile/photo/", views.update_profile_photo, name="update_profile_photo"),
]
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

   

    path("profile/photo/", views.update_profile_photo, name="update_profile_photo"),
    
    path("subscribe/", views.subscribe, name="subscribe"),
    path("subscribe/verify/", views.verify_payment, name="verify_payment"),
    path("listing/<int:pk>/pay-rent/", views.pay_rent, name="pay_rent"),
    path("payments/<int:pk>/receipt/", views.download_receipt, name="download_receipt"),
    
     path("subscribe/", views.subscribe, name="subscribe"),
    path("subscribe/verify/", views.verify_payment, name="verify_payment"),
 
    path("listing/<int:pk>/pay-rent/", views.pay_rent, name="pay_rent"),
 
    path("staff/dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("staff/verification/<int:pk>/approve/", views.approve_verification, name="approve_verification"),
    path("staff/verification/<int:pk>/reject/", views.reject_verification, name="reject_verification"),
    
    path("subscribe/", views.subscribe, name="subscribe"),
    path("subscribe/verify/", views.verify_payment, name="verify_payment"),
 
    path("listing/<int:pk>/pay-rent/", views.pay_rent, name="pay_rent"),
 
    path("staff/dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("staff/verification/<int:pk>/approve/", views.approve_verification, name="approve_verification"),
    path("staff/verification/<int:pk>/reject/", views.reject_verification, name="reject_verification"),
    path("staff/listing/<int:pk>/approve/", views.approve_listing, name="approve_listing"),
    path("staff/listing/<int:pk>/archive/", views.archive_listing, name="archive_listing"),
    path("staff/user/<int:pk>/toggle-active/", views.toggle_user_active, name="toggle_user_active"),
    path("staff/payments/export/", views.export_payments_csv, name="export_payments_csv"),
    path("payments/<int:pk>/receipt/", views.download_receipt, name="download_receipt"),
    path("staff/payments/export/", views.export_payments_csv, name="export_payments_csv"),
        path("subscribe/", views.subscribe, name="subscribe"),
    path("subscribe/verify/", views.verify_payment, name="verify_payment"),
 
    path("listing/<int:pk>/pay-rent/", views.pay_rent, name="pay_rent"),
 
    path("staff/dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("staff/verification/<int:pk>/approve/", views.approve_verification, name="approve_verification"),
    path("staff/verification/<int:pk>/reject/", views.reject_verification, name="reject_verification"),
    path("staff/listing/<int:pk>/approve/", views.approve_listing, name="approve_listing"),
    path("staff/listing/<int:pk>/archive/", views.archive_listing, name="archive_listing"),
    path("staff/listing/<int:pk>/toggle-featured/", views.toggle_featured_listing, name="toggle_featured_listing"),
    path("staff/user/<int:pk>/toggle-active/", views.toggle_user_active, name="toggle_user_active"),
    path("staff/payments/export/", views.export_payments_csv, name="export_payments_csv"),
    path("payments/<int:pk>/receipt/", views.download_receipt, name="download_receipt"),
    path("subscribe/", views.subscribe, name="subscribe"),
    path("subscribe/verify/", views.verify_payment, name="verify_payment"),
 
    path("listing/<int:pk>/pay-rent/", views.pay_rent, name="pay_rent"),
 
    



 
]
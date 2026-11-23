from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("users", views.UserViewSet, basename="user")
router.register("permission-sets", views.PermissionSetViewSet, basename="permission-set")

urlpatterns = [
    path("auth/csrf/", views.CsrfView.as_view(), name="auth-csrf"),
    path("auth/login/", views.LoginView.as_view(), name="auth-login"),
    path("auth/otp/request/", views.OTPRequestView.as_view(), name="auth-otp-request"),
    path("auth/otp/verify/", views.OTPVerifyView.as_view(), name="auth-otp-verify"),
    path("auth/mfa/verify/", views.MFAVerifyView.as_view(), name="auth-mfa-verify"),
    path("auth/mfa/setup/", views.MFASetupView.as_view(), name="auth-mfa-setup"),
    path("auth/mfa/confirm/", views.MFAConfirmView.as_view(), name="auth-mfa-confirm"),
    path("auth/mfa/disable/", views.MFADisableView.as_view(), name="auth-mfa-disable"),
    path("auth/refresh/", views.RefreshView.as_view(), name="auth-refresh"),
    path("auth/logout/", views.LogoutView.as_view(), name="auth-logout"),
    path("auth/password/reset/", views.PasswordResetRequestView.as_view(), name="auth-password-reset"),
    path("auth/password/set/", views.PasswordSetView.as_view(), name="auth-password-set"),
    path("auth/password/change/", views.PasswordChangeView.as_view(), name="auth-password-change"),
    path("auth/me/", views.MeView.as_view(), name="auth-me"),
    path("capabilities/", views.CapabilityListView.as_view(), name="capabilities"),
    path("roles/matrix/", views.RoleMatrixView.as_view(), name="role-matrix"),
    *router.urls,
]

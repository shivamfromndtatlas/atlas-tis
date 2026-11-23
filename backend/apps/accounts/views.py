from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.audit.services import record as audit
from apps.core.context import set_actor
from apps.core.exceptions import TISError, error_response
from apps.core.permissions import HasCapability

from . import services
from .models import PermissionSet, Role, User
from .serializers import (
    CapabilitySerializer,
    LoginSerializer,
    MeSerializer,
    MFACodeSerializer,
    MFADisableSerializer,
    MFAVerifySerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    PasswordChangeSerializer,
    PasswordResetRequestSerializer,
    PasswordSetSerializer,
    PermissionSetSerializer,
    RoleMatrixRowSerializer,
    UserAdminSerializer,
    all_capabilities,
)
from .tokens import clear_auth_cookies, issue_tokens, set_auth_cookies


def _session_response(request, user, status_code=200):
    """Log the user in: issue cookies and return the /me payload."""
    user.last_login = timezone.now()
    user.save(update_fields=["last_login"])
    set_actor(user)
    audit("auth.login", user, actor=user)
    response = Response({"user": MeSerializer(user).data}, status=status_code)
    return set_auth_cookies(response, request, issue_tokens(user))


def _after_primary_auth(request, user):
    """Either finish login, or ask for the second factor when MFA is enrolled."""
    if user.mfa_enabled:
        return Response({"mfa_required": True, "challenge": services.mfa_challenge_for(user)})
    return _session_response(request, user)


class AuthThrottleMixin:
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"


@method_decorator(ensure_csrf_cookie, name="get")
class CsrfView(APIView):
    """Sets the CSRF cookie the SPA must echo in X-CSRFToken."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(responses={204: None})
    def get(self, request):
        return Response(status=status.HTTP_204_NO_CONTENT)


class LoginView(AuthThrottleMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(
        request=LoginSerializer, responses={200: OpenApiResponse(description="User or MFA challenge")}
    )
    def post(self, request):
        data = LoginSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        email = data.validated_data["email"].strip().lower()
        user = User.objects.filter(email=email).first()
        if user is None or not user.is_active or not user.check_password(data.validated_data["password"]):
            audit("auth.login_failed", user, {"email": email}, actor=None)
            return error_response("INVALID_CREDENTIALS", "Email or password is incorrect.")
        return _after_primary_auth(request, user)


class OTPRequestView(AuthThrottleMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_scope = "otp"

    @extend_schema(request=OTPRequestSerializer, responses={202: None})
    def post(self, request):
        data = OTPRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.issue_otp(data.validated_data["email"])
        # Same answer whether or not the account exists.
        return Response({"detail": "If an account exists, a code has been sent."}, status=202)


class OTPVerifyView(AuthThrottleMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(
        request=OTPVerifySerializer, responses={200: OpenApiResponse(description="User or MFA challenge")}
    )
    def post(self, request):
        data = OTPVerifySerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = services.verify_otp(data.validated_data["email"], data.validated_data["code"])
        if user is None:  # returned, not raised, so the attempt counter is persisted
            return error_response("INVALID_OTP", "The code is invalid or has expired.")
        return _after_primary_auth(request, user)


class MFAVerifyView(AuthThrottleMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(request=MFAVerifySerializer, responses={200: MeSerializer})
    def post(self, request):
        data = MFAVerifySerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = services.user_from_mfa_challenge(data.validated_data["challenge"])
        if user is None:
            raise TISError(
                "Sign-in expired. Please start again.", code="MFA_CHALLENGE_EXPIRED", status_code=400
            )
        if not services.verify_totp(user, data.validated_data["code"]):
            audit("auth.mfa_failed", user, actor=user)
            return error_response("INVALID_MFA_CODE", "The authentication code is incorrect.")
        return _session_response(request, user)


class RefreshView(AuthThrottleMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        raw = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH)
        if not raw:
            raise TISError("Not signed in.", code="NOT_AUTHENTICATED", status_code=401)
        try:
            old = RefreshToken(raw)
            user = User.objects.get(pk=old["uid"], is_active=True)
            if old.get("tv") != user.token_version:
                raise TokenError("revoked")
            old.blacklist()
        except (TokenError, User.DoesNotExist, KeyError):
            response = Response(
                {"error": {"code": "SESSION_EXPIRED", "message": "Session expired.", "details": None}},
                status=401,
            )
            return clear_auth_cookies(response)
        response = Response(status=status.HTTP_204_NO_CONTENT)
        return set_auth_cookies(response, request, issue_tokens(user))


class LogoutView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        raw = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH)
        if raw:
            try:
                RefreshToken(raw).blacklist()
            except TokenError:
                pass
        if request.user.is_authenticated:
            audit("auth.logout", request.user)
        return clear_auth_cookies(Response(status=status.HTTP_204_NO_CONTENT))


class PasswordResetRequestView(AuthThrottleMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_scope = "otp"

    @extend_schema(request=PasswordResetRequestSerializer, responses={202: None})
    def post(self, request):
        data = PasswordResetRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.send_password_reset(data.validated_data["email"])
        return Response({"detail": "If an account exists, a reset link has been sent."}, status=202)


class PasswordSetView(AuthThrottleMixin, APIView):
    """Completes both invite acceptance and password reset (signed one-time link)."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(request=PasswordSetSerializer, responses={200: MeSerializer})
    def post(self, request):
        data = PasswordSetSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = services.user_from_link(str(data.validated_data["uid"]), data.validated_data["token"])
        if user is None:
            raise TISError("This link is invalid or has expired.", code="INVALID_LINK", status_code=400)
        try:
            validate_password(data.validated_data["password"], user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        user.set_password(data.validated_data["password"])
        now = timezone.now()
        user.invite_accepted_at = user.invite_accepted_at or now
        user.email_verified_at = user.email_verified_at or now
        user.revoke_tokens()
        user.save()
        audit("auth.password_set", user, actor=user)
        return _after_primary_auth(request, user)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=MeSerializer)
    def get(self, request):
        return Response(MeSerializer(request.user).data)

    @extend_schema(request=MeSerializer, responses=MeSerializer)
    def patch(self, request):
        serializer = MeSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=PasswordChangeSerializer, responses={200: MeSerializer})
    def post(self, request):
        data = PasswordChangeSerializer(data=request.data, context={"request": request})
        data.is_valid(raise_exception=True)
        user = request.user
        user.set_password(data.validated_data["new_password"])
        user.revoke_tokens()
        user.save()
        audit("auth.password_changed", user)
        return _session_response(request, user)  # fresh tokens for this device; others are revoked


class MFASetupView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={200: OpenApiResponse(description="{otpauth_uri, secret}")})
    def post(self, request):
        if request.user.mfa_enabled:
            raise TISError("MFA is already enabled.", code="MFA_ALREADY_ENABLED")
        uri = services.start_mfa_setup(request.user)
        return Response({"otpauth_uri": uri, "secret": request.user.mfa_secret})


class MFAConfirmView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=MFACodeSerializer, responses={200: MeSerializer})
    def post(self, request):
        data = MFACodeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = request.user
        if not user.mfa_secret or not services.verify_totp(user, data.validated_data["code"]):
            raise TISError("The authentication code is incorrect.", code="INVALID_MFA_CODE")
        user.mfa_enabled = True
        user.save(update_fields=["mfa_enabled"])
        audit("auth.mfa_enabled", user)
        return Response(MeSerializer(user).data)


class MFADisableView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=MFADisableSerializer, responses={200: MeSerializer})
    def post(self, request):
        data = MFADisableSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = request.user
        if user.mfa_required:
            raise TISError("MFA is mandatory for your role.", code="MFA_MANDATORY", status_code=403)
        if not user.check_password(data.validated_data["password"]) or not services.verify_totp(
            user, data.validated_data["code"]
        ):
            raise TISError("Password or code is incorrect.", code="INVALID_CREDENTIALS")
        user.mfa_enabled = False
        user.mfa_secret = ""
        user.save(update_fields=["mfa_enabled", "mfa_secret"])
        audit("auth.mfa_disabled", user)
        return Response(MeSerializer(user).data)


# --- Administration ---------------------------------------------------------------
class UserViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """User administration. Users are never hard-deleted: set ``is_active=false``."""

    serializer_class = UserAdminSerializer
    permission_classes = [HasCapability]
    capability_map = {
        "list": ("users.view", "users.invite_external"),
        "retrieve": ("users.view", "users.invite_external"),
        "create": ("users.manage", "users.invite_external"),
        "update": ("users.manage", "users.invite_external"),
        "partial_update": ("users.manage", "users.invite_external"),
        "resend_invite": ("users.manage", "users.invite_external"),
        "reset_mfa": "users.manage",
    }
    lookup_field = "public_id"
    lookup_url_kwarg = "id"
    filterset_fields = ["role", "is_active"]
    search_fields = ["email", "first_name", "last_name"]
    ordering_fields = ["email", "first_name", "date_joined", "last_login"]

    def get_queryset(self):
        qs = User.objects.select_related("client", "agency").prefetch_related("permission_sets")
        if getattr(self, "swagger_fake_view", False):
            return qs.none()
        user = self.request.user
        if user.has_capability("users.view") or user.has_capability("users.manage"):
            pass
        else:  # invite_external only: external accounts
            qs = qs.filter(role__in=[Role.CLIENT_USER, Role.CONSULTANT])
        client = self.request.query_params.get("client")
        if client:
            qs = qs.filter(client__public_id=client)
        agency = self.request.query_params.get("agency")
        if agency:
            qs = qs.filter(agency__public_id=agency)
        return qs

    @extend_schema(request=None, responses={202: None})
    @action(detail=True, methods=["post"], url_path="resend-invite")
    def resend_invite(self, request, id=None):
        user = self.get_object()
        if user.invite_accepted_at is not None or user.has_usable_password():
            raise TISError("This user has already accepted the invite.", code="INVITE_ALREADY_ACCEPTED")
        services.send_invite(user, request.user)
        return Response(status=202)

    @extend_schema(request=None, responses={200: UserAdminSerializer})
    @action(detail=True, methods=["post"], url_path="reset-mfa")
    def reset_mfa(self, request, id=None):
        user = self.get_object()
        user.mfa_enabled = False
        user.mfa_secret = ""
        user.revoke_tokens()
        user.save()
        audit("auth.mfa_reset_by_admin", user)
        return Response(self.get_serializer(user).data)


class PermissionSetViewSet(viewsets.ModelViewSet):
    """Add-on permission sets and custom roles. Role default sets are edited via the role matrix."""

    serializer_class = PermissionSetSerializer
    permission_classes = [HasCapability]
    capability_map = {
        "list": ("users.view", "roles.manage"),
        "retrieve": ("users.view", "roles.manage"),
        "*": "roles.manage",
    }
    queryset = PermissionSet.objects.filter(role_default__isnull=True)

    def perform_destroy(self, instance):
        if instance.is_system:
            raise TISError("System permission sets cannot be deleted.", code="SYSTEM_SET", status_code=409)
        if instance.users.exists():
            raise TISError("Remove this set from all users first.", code="SET_IN_USE", status_code=409)
        instance.delete()

    def perform_update(self, serializer):
        instance = serializer.save()
        # Capabilities are evaluated per request, so no token revocation is needed.
        return instance


class CapabilityListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=CapabilitySerializer(many=True))
    def get(self, request):
        return Response(all_capabilities())


class RoleMatrixView(APIView):
    """GET the default capabilities of every role; PUT one role's capabilities."""

    permission_classes = [HasCapability]
    capability_map = {"get": ("users.view", "roles.manage"), "put": "roles.manage"}

    def _rows(self):
        sets = {s.role_default: s for s in PermissionSet.objects.filter(role_default__isnull=False)}
        rows = []
        for role, label in Role.choices:
            if role == Role.SUPER_ADMIN:
                rows.append(
                    {"role": role, "label": label, "capabilities": sorted(all_codes()), "editable": False}
                )
            else:
                caps = sets[role].capabilities if role in sets else []
                rows.append({"role": role, "label": label, "capabilities": caps, "editable": True})
        return rows

    @extend_schema(responses=RoleMatrixRowSerializer(many=True))
    def get(self, request):
        return Response(self._rows())

    @extend_schema(request=RoleMatrixRowSerializer, responses=RoleMatrixRowSerializer(many=True))
    def put(self, request):
        data = RoleMatrixRowSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        role = data.validated_data["role"]
        if role == Role.SUPER_ADMIN:
            raise TISError("Super Admin always has every capability.", code="NOT_EDITABLE", status_code=409)
        perm_set, _ = PermissionSet.objects.get_or_create(
            role_default=role,
            defaults={
                "code": f"role-{role.lower()}",
                "name": f"{Role(role).label} (default)",
                "is_system": True,
            },
        )
        perm_set.capabilities = data.validated_data["capabilities"]
        perm_set.save()
        return Response(self._rows())


def all_codes():
    from .capabilities import CAPABILITY_CODES

    return CAPABILITY_CODES

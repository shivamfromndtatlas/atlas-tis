"""Cookie-based JWT authentication with CSRF enforcement and token-version revocation."""

from django.conf import settings
from rest_framework import exceptions
from rest_framework.authentication import CSRFCheck
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.core.context import set_actor


def _enforce_csrf(request) -> None:
    def dummy_get_response(_request):  # pragma: no cover
        return None

    check = CSRFCheck(dummy_get_response)
    check.process_request(request)
    reason = check.process_view(request, None, (), {})
    if reason:
        raise exceptions.PermissionDenied(f"CSRF failed: {reason}")


class CookieJWTAuthentication(JWTAuthentication):
    """Reads the access token from the httpOnly cookie (or an Authorization header for API clients).

    Cookie-authenticated unsafe requests must carry a valid X-CSRFToken header.
    Tokens whose ``tv`` claim is older than ``user.token_version`` are rejected.
    """

    def authenticate(self, request):
        header = self.get_header(request)
        from_cookie = False
        if header is not None:
            raw_token = self.get_raw_token(header)
        else:
            raw_token = request.COOKIES.get(settings.AUTH_COOKIE_ACCESS)
            from_cookie = True
        if not raw_token:
            return None

        validated = self.get_validated_token(raw_token)
        user = self.get_user(validated)
        if not user.is_active:
            raise exceptions.AuthenticationFailed("Account disabled.", code="account_disabled")
        if validated.get("tv") != user.token_version:
            raise exceptions.AuthenticationFailed(
                "Session expired. Please sign in again.", code="token_revoked"
            )
        if from_cookie:
            _enforce_csrf(request)
        set_actor(user)
        return user, validated

    def authenticate_header(self, request):
        return 'Bearer realm="api"'

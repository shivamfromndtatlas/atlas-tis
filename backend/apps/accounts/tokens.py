"""JWT issuing and httpOnly cookie helpers."""

from django.conf import settings
from django.middleware.csrf import get_token
from rest_framework_simplejwt.tokens import RefreshToken


def issue_tokens(user) -> RefreshToken:
    refresh = RefreshToken.for_user(user)
    # Copied into the access token too. "tv" lets us revoke every token by bumping token_version.
    refresh["tv"] = user.token_version
    refresh["role"] = user.role
    return refresh


def _cookie_kwargs() -> dict:
    return {
        "httponly": True,
        "secure": settings.AUTH_COOKIE_SECURE,
        "samesite": settings.AUTH_COOKIE_SAMESITE,
        "domain": settings.AUTH_COOKIE_DOMAIN,
    }


def set_auth_cookies(response, request, refresh: RefreshToken):
    jwt = settings.SIMPLE_JWT
    response.set_cookie(
        settings.AUTH_COOKIE_ACCESS,
        str(refresh.access_token),
        max_age=int(jwt["ACCESS_TOKEN_LIFETIME"].total_seconds()),
        path="/",
        **_cookie_kwargs(),
    )
    response.set_cookie(
        settings.AUTH_COOKIE_REFRESH,
        str(refresh),
        max_age=int(jwt["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        path="/api/v1/auth/",
        **_cookie_kwargs(),
    )
    get_token(request)  # rotate/ensure CSRF cookie for the SPA
    return response


def clear_auth_cookies(response):
    response.delete_cookie(settings.AUTH_COOKIE_ACCESS, path="/", domain=settings.AUTH_COOKIE_DOMAIN)
    response.delete_cookie(
        settings.AUTH_COOKIE_REFRESH, path="/api/v1/auth/", domain=settings.AUTH_COOKIE_DOMAIN
    )
    return response

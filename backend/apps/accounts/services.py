"""Account services: OTP, MFA, invites and password reset."""

from __future__ import annotations

import secrets
from datetime import timedelta

import pyotp
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.tokens import default_token_generator
from django.core import signing
from django.core.mail import send_mail
from django.utils import timezone

from apps.audit.services import record as audit

from .models import OTPChallenge, User

MFA_SALT = "tis.mfa-challenge"


# --- Email OTP -----------------------------------------------------------------
def issue_otp(email: str, purpose: str = OTPChallenge.Purpose.LOGIN) -> None:
    """Create and send an OTP. Silent when the account does not exist (no user enumeration)."""
    email = email.strip().lower()
    user = User.objects.filter(email=email, is_active=True).first()
    if user is None:
        return
    code = "".join(secrets.choice("0123456789") for _ in range(settings.OTP_LENGTH))
    OTPChallenge.objects.filter(target=email, purpose=purpose, consumed_at__isnull=True).update(
        consumed_at=timezone.now()
    )
    OTPChallenge.objects.create(
        target=email,
        purpose=purpose,
        code_hash=make_password(code),
        expires_at=timezone.now() + timedelta(seconds=settings.OTP_TTL_SECONDS),
    )
    minutes = settings.OTP_TTL_SECONDS // 60
    send_mail(
        subject=f"Your NDT Atlas verification code: {code}",
        message=f"Your verification code is {code}. It expires in {minutes} minutes.\n\n"
        "If you did not request this, you can ignore this email.",
        from_email=None,
        recipient_list=[email],
    )


def verify_otp(email: str, code: str, purpose: str = OTPChallenge.Purpose.LOGIN) -> User | None:
    email = email.strip().lower()
    challenge = (
        OTPChallenge.objects.filter(target=email, purpose=purpose, consumed_at__isnull=True)
        .order_by("-created_at")
        .first()
    )
    if challenge is None or not challenge.is_usable:
        return None
    if not check_password(code.strip(), challenge.code_hash):
        challenge.attempts += 1
        challenge.save(update_fields=["attempts"])
        return None
    challenge.consumed_at = timezone.now()
    challenge.save(update_fields=["consumed_at"])
    user = User.objects.filter(email=email, is_active=True).first()
    if user and user.email_verified_at is None:
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified_at"])
    return user


# --- MFA (TOTP) ------------------------------------------------------------------
def mfa_challenge_for(user: User) -> str:
    return signing.dumps({"uid": user.pk, "tv": user.token_version}, salt=MFA_SALT)


def user_from_mfa_challenge(token: str) -> User | None:
    try:
        data = signing.loads(token, salt=MFA_SALT, max_age=settings.MFA_CHALLENGE_TTL_SECONDS)
    except signing.BadSignature:
        return None
    user = User.objects.filter(pk=data["uid"], is_active=True).first()
    if user is None or user.token_version != data["tv"]:
        return None
    return user


def verify_totp(user: User, code: str) -> bool:
    if not user.mfa_secret:
        return False
    return pyotp.TOTP(user.mfa_secret).verify(code.strip(), valid_window=1)


def start_mfa_setup(user: User) -> str:
    user.mfa_secret = pyotp.random_base32()
    user.mfa_enabled = False
    user.save(update_fields=["mfa_secret", "mfa_enabled"])
    return pyotp.TOTP(user.mfa_secret).provisioning_uri(name=user.email, issuer_name=settings.MFA_ISSUER)


# --- Invites and password reset --------------------------------------------------
def _link(path: str, user: User) -> str:
    token = default_token_generator.make_token(user)
    return f"{settings.FRONTEND_URL}{path}?uid={user.public_id}&token={token}"


def send_invite(user: User, invited_by: User | None = None) -> None:
    link = _link("/accept-invite", user)
    inviter = invited_by.full_name if invited_by else "NDT Atlas"
    send_mail(
        subject="You have been invited to NDT Atlas Talent Intelligence System",
        message=f"Hello {user.first_name or ''},\n\n{inviter} has invited you to the NDT Atlas TIS.\n"
        f"Set your password here: {link}\n\nThis link expires in 3 days.",
        from_email=None,
        recipient_list=[user.email],
    )
    audit("user.invite_sent", user)


def send_password_reset(email: str) -> None:
    user = User.objects.filter(email=email.strip().lower(), is_active=True).first()
    if user is None:
        return
    link = _link("/reset-password", user)
    send_mail(
        subject="Reset your NDT Atlas password",
        message=f"Reset your password here: {link}\n\nIf you did not request this, ignore this email.",
        from_email=None,
        recipient_list=[user.email],
    )
    audit("user.password_reset_requested", user)


def user_from_link(uid: str, token: str) -> User | None:
    try:
        user = User.objects.get(public_id=uid, is_active=True)
    except Exception:  # unknown user, or a malformed UUID (Django raises ValidationError)
        return None
    return user if default_token_generator.check_token(user, token) else None

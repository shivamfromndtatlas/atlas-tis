import re

import pyotp
import pytest
from django.conf import settings
from django.core import mail
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.audit.models import AuditLog

from .conftest import PASSWORD, login

pytestmark = pytest.mark.django_db


def test_password_login_sets_httponly_cookies_and_me_works(api, make_user):
    user = make_user(Role.ATLAS_RECRUITER)
    response = login(api, user)
    access = response.cookies[settings.AUTH_COOKIE_ACCESS]
    assert access["httponly"]
    assert settings.AUTH_COOKIE_REFRESH in response.cookies
    me = api.get("/api/v1/auth/me/")
    assert me.status_code == 200
    assert me.json()["email"] == user.email
    assert "clients.view" in me.json()["capabilities"]


def test_wrong_password_is_generic_and_audited(api, make_user):
    user = make_user()
    response = api.post("/api/v1/auth/login/", {"email": user.email, "password": "nope"}, format="json")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"
    unknown = api.post("/api/v1/auth/login/", {"email": "ghost@test.local", "password": "x"}, format="json")
    assert unknown.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert AuditLog.objects.filter(action="auth.login_failed").count() == 2


def test_disabled_user_cannot_login(api, make_user):
    user = make_user(is_active=False)
    response = api.post("/api/v1/auth/login/", {"email": user.email, "password": PASSWORD}, format="json")
    assert response.status_code == 400


def test_unauthenticated_requests_are_rejected(api):
    assert api.get("/api/v1/auth/me/").status_code == 401


def test_otp_login_flow(api, make_user):
    user = make_user(Role.CANDIDATE)
    assert api.post("/api/v1/auth/otp/request/", {"email": user.email}, format="json").status_code == 202
    assert len(mail.outbox) == 1
    code = re.search(r"\b(\d{6})\b", mail.outbox[0].subject).group(1)

    bad = api.post("/api/v1/auth/otp/verify/", {"email": user.email, "code": "000000"}, format="json")
    if code != "000000":
        assert bad.status_code == 400
    ok = api.post("/api/v1/auth/otp/verify/", {"email": user.email, "code": code}, format="json")
    assert ok.status_code == 200
    assert api.get("/api/v1/auth/me/").status_code == 200
    user.refresh_from_db()
    assert user.email_verified_at is not None
    # one-time use
    again = APIClient().post("/api/v1/auth/otp/verify/", {"email": user.email, "code": code}, format="json")
    assert again.status_code == 400


def test_otp_request_does_not_reveal_unknown_accounts(api):
    response = api.post("/api/v1/auth/otp/request/", {"email": "nobody@test.local"}, format="json")
    assert response.status_code == 202
    assert len(mail.outbox) == 0


def test_otp_locks_after_max_attempts(api, make_user):
    user = make_user()
    api.post("/api/v1/auth/otp/request/", {"email": user.email}, format="json")
    code = re.search(r"\b(\d{6})\b", mail.outbox[0].subject).group(1)
    wrong = "111111" if code != "111111" else "222222"
    for _ in range(settings.OTP_MAX_ATTEMPTS):
        api.post("/api/v1/auth/otp/verify/", {"email": user.email, "code": wrong}, format="json")
    response = api.post("/api/v1/auth/otp/verify/", {"email": user.email, "code": code}, format="json")
    assert response.status_code == 400


def test_mfa_enrolment_and_login(api, make_user):
    user = make_user(Role.SUPER_ADMIN)
    login(api, user)
    assert api.get("/api/v1/auth/me/").json()["mfa_setup_required"] is True

    setup = api.post("/api/v1/auth/mfa/setup/")
    secret = setup.json()["secret"]
    confirm = api.post("/api/v1/auth/mfa/confirm/", {"code": pyotp.TOTP(secret).now()}, format="json")
    assert confirm.status_code == 200 and confirm.json()["mfa_enabled"] is True

    fresh = APIClient()
    first = fresh.post("/api/v1/auth/login/", {"email": user.email, "password": PASSWORD}, format="json")
    assert first.json()["mfa_required"] is True
    assert settings.AUTH_COOKIE_ACCESS not in first.cookies
    challenge = first.json()["challenge"]
    wrong = fresh.post("/api/v1/auth/mfa/verify/", {"challenge": challenge, "code": "123456"}, format="json")
    if pyotp.TOTP(secret).now() != "123456":
        assert wrong.status_code == 400
    ok = fresh.post(
        "/api/v1/auth/mfa/verify/", {"challenge": challenge, "code": pyotp.TOTP(secret).now()}, format="json"
    )
    assert ok.status_code == 200
    assert fresh.get("/api/v1/auth/me/").status_code == 200


def test_mandatory_mfa_cannot_be_disabled(api, make_user):
    user = make_user(Role.SUPER_ADMIN)
    login(api, user)
    secret = api.post("/api/v1/auth/mfa/setup/").json()["secret"]
    api.post("/api/v1/auth/mfa/confirm/", {"code": pyotp.TOTP(secret).now()}, format="json")
    response = api.post(
        "/api/v1/auth/mfa/disable/", {"password": PASSWORD, "code": pyotp.TOTP(secret).now()}, format="json"
    )
    assert response.status_code == 403


def test_refresh_rotates_and_blacklists_old_token(api, make_user):
    user = make_user()
    login(api, user)
    old_refresh = api.cookies[settings.AUTH_COOKIE_REFRESH].value
    assert api.post("/api/v1/auth/refresh/").status_code == 204
    assert api.cookies[settings.AUTH_COOKIE_REFRESH].value != old_refresh
    replay = APIClient()
    replay.cookies[settings.AUTH_COOKIE_REFRESH] = old_refresh
    assert replay.post("/api/v1/auth/refresh/").status_code == 401


def test_logout_revokes_refresh(api, make_user):
    user = make_user()
    login(api, user)
    refresh = api.cookies[settings.AUTH_COOKIE_REFRESH].value
    assert api.post("/api/v1/auth/logout/").status_code == 204
    replay = APIClient()
    replay.cookies[settings.AUTH_COOKIE_REFRESH] = refresh
    assert replay.post("/api/v1/auth/refresh/").status_code == 401


def test_role_change_revokes_existing_sessions(users, make_user):
    target = users["ATLAS_RECRUITER"]
    victim_session = APIClient()
    login(victim_session, target)
    assert victim_session.get("/api/v1/auth/me/").status_code == 200

    admin = APIClient()
    login(admin, users["SUPER_ADMIN"])
    response = admin.patch(f"/api/v1/users/{target.public_id}/", {"role": Role.CANDIDATE}, format="json")
    assert response.status_code == 200, response.content
    assert victim_session.get("/api/v1/auth/me/").status_code == 401
    assert victim_session.post("/api/v1/auth/refresh/").status_code == 401


def test_password_reset_flow(api, make_user):
    user = make_user()
    api.post("/api/v1/auth/password/reset/", {"email": user.email}, format="json")
    body = mail.outbox[0].body
    uid = re.search(r"uid=([0-9a-f-]+)", body).group(1)
    token = re.search(r"token=([\w-]+)", body).group(1)
    weak = api.post(
        "/api/v1/auth/password/set/", {"uid": uid, "token": token, "password": "short"}, format="json"
    )
    assert weak.status_code == 400
    new_password = "Another-Long-Passw0rd!"
    ok = api.post(
        "/api/v1/auth/password/set/", {"uid": uid, "token": token, "password": new_password}, format="json"
    )
    assert ok.status_code == 200
    reuse = APIClient().post(
        "/api/v1/auth/password/set/",
        {"uid": uid, "token": token, "password": "Yet-Another-Passw0rd!"},
        format="json",
    )
    assert reuse.status_code == 400  # token is single-use (password hash changed)
    login(APIClient(), user, password=new_password)


def test_invite_acceptance(users, django_capture_on_commit_callbacks):
    admin = APIClient()
    login(admin, users["SUPER_ADMIN"])
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        created = admin.post(
            "/api/v1/users/",
            {"email": "New.Recruiter@Test.local", "first_name": "New", "role": Role.ATLAS_RECRUITER},
            format="json",
        )
    assert created.status_code == 201, created.content
    assert created.json()["email"] == "new.recruiter@test.local"
    assert created.json()["invite_pending"] is True
    body = mail.outbox[0].body
    uid = re.search(r"uid=([0-9a-f-]+)", body).group(1)
    token = re.search(r"token=([\w-]+)", body).group(1)
    accept = APIClient().post(
        "/api/v1/auth/password/set/",
        {"uid": uid, "token": token, "password": "Invited-Passw0rd-123"},
        format="json",
    )
    assert accept.status_code == 200
    assert accept.json()["user"]["email"] == "new.recruiter@test.local"


def test_cookie_auth_requires_csrf_header_for_unsafe_methods(make_user):
    user = make_user(Role.SUPER_ADMIN)
    strict = APIClient(enforce_csrf_checks=True)
    strict.get("/api/v1/auth/csrf/")
    csrf = strict.cookies["csrftoken"].value
    response = strict.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": PASSWORD},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )
    assert response.status_code == 200
    csrf = strict.cookies["csrftoken"].value
    payload = {"name": "CSRF Co"}
    assert strict.post("/api/v1/clients/", payload, format="json").status_code == 403
    assert strict.post("/api/v1/clients/", payload, format="json", HTTP_X_CSRFTOKEN=csrf).status_code == 201

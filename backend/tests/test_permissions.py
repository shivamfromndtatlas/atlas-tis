"""Role x endpoint permission matrix (spec section 3.2 / 18). Generated from one table."""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role

from .conftest import login

pytestmark = pytest.mark.django_db

ROLES = ["SUPER_ADMIN", "ATLAS_LEAD", "ATLAS_RECRUITER", "CLIENT_USER", "CONSULTANT", "CANDIDATE"]

# (method, path, body, {role: expected status})
OK, CREATED, FORBIDDEN = 200, 201, 403
MATRIX = [
    (
        "get",
        "/api/v1/users/",
        None,
        dict(
            SUPER_ADMIN=OK,
            ATLAS_LEAD=OK,
            ATLAS_RECRUITER=FORBIDDEN,
            CLIENT_USER=FORBIDDEN,
            CONSULTANT=FORBIDDEN,
            CANDIDATE=FORBIDDEN,
        ),
    ),
    (
        "get",
        "/api/v1/clients/",
        None,
        dict(
            SUPER_ADMIN=OK,
            ATLAS_LEAD=OK,
            ATLAS_RECRUITER=OK,
            CLIENT_USER=OK,
            CONSULTANT=FORBIDDEN,
            CANDIDATE=FORBIDDEN,
        ),
    ),
    (
        "post",
        "/api/v1/clients/",
        {"name": "New Co"},
        dict(
            SUPER_ADMIN=CREATED,
            ATLAS_LEAD=CREATED,
            ATLAS_RECRUITER=FORBIDDEN,
            CLIENT_USER=FORBIDDEN,
            CONSULTANT=FORBIDDEN,
            CANDIDATE=FORBIDDEN,
        ),
    ),
    (
        "get",
        "/api/v1/agencies/",
        None,
        dict(
            SUPER_ADMIN=OK,
            ATLAS_LEAD=OK,
            ATLAS_RECRUITER=OK,
            CLIENT_USER=FORBIDDEN,
            CONSULTANT=OK,
            CANDIDATE=FORBIDDEN,
        ),
    ),
    (
        "post",
        "/api/v1/agencies/",
        {"name": "New Agency"},
        dict(
            SUPER_ADMIN=CREATED,
            ATLAS_LEAD=CREATED,
            ATLAS_RECRUITER=FORBIDDEN,
            CLIENT_USER=FORBIDDEN,
            CONSULTANT=FORBIDDEN,
            CANDIDATE=FORBIDDEN,
        ),
    ),
    (
        "get",
        "/api/v1/audit/",
        None,
        dict(
            SUPER_ADMIN=OK,
            ATLAS_LEAD=OK,
            ATLAS_RECRUITER=FORBIDDEN,
            CLIENT_USER=FORBIDDEN,
            CONSULTANT=FORBIDDEN,
            CANDIDATE=FORBIDDEN,
        ),
    ),
    (
        "get",
        "/api/v1/roles/matrix/",
        None,
        dict(
            SUPER_ADMIN=OK,
            ATLAS_LEAD=OK,
            ATLAS_RECRUITER=FORBIDDEN,
            CLIENT_USER=FORBIDDEN,
            CONSULTANT=FORBIDDEN,
            CANDIDATE=FORBIDDEN,
        ),
    ),
    (
        "put",
        "/api/v1/roles/matrix/",
        {"role": "CANDIDATE", "capabilities": ["files.upload"]},
        dict(
            SUPER_ADMIN=OK,
            ATLAS_LEAD=FORBIDDEN,
            ATLAS_RECRUITER=FORBIDDEN,
            CLIENT_USER=FORBIDDEN,
            CONSULTANT=FORBIDDEN,
            CANDIDATE=FORBIDDEN,
        ),
    ),
    (
        "post",
        "/api/v1/permission-sets/",
        {"code": "custom", "name": "Custom", "capabilities": ["clients.view"]},
        dict(
            SUPER_ADMIN=CREATED,
            ATLAS_LEAD=FORBIDDEN,
            ATLAS_RECRUITER=FORBIDDEN,
            CLIENT_USER=FORBIDDEN,
            CONSULTANT=FORBIDDEN,
            CANDIDATE=FORBIDDEN,
        ),
    ),
    (
        "get",
        "/api/v1/files/",
        None,
        dict(SUPER_ADMIN=OK, ATLAS_LEAD=OK, ATLAS_RECRUITER=OK, CLIENT_USER=OK, CONSULTANT=OK, CANDIDATE=OK),
    ),
]

CASES = [
    pytest.param(method, path, body, role, expected[role], id=f"{role}-{method}-{path}")
    for method, path, body, expected in MATRIX
    for role in ROLES
]


@pytest.mark.parametrize(("method", "path", "body", "role", "expected"), CASES)
def test_permission_matrix(users, method, path, body, role, expected):
    api = APIClient()
    login(api, users[role])
    response = getattr(api, method)(path, body, format="json") if body else getattr(api, method)(path)
    assert response.status_code == expected, response.content


def test_matrix_edit_takes_effect_immediately(users):
    candidate = APIClient()
    login(candidate, users["CANDIDATE"])
    assert candidate.get("/api/v1/clients/").status_code == 403

    admin = APIClient()
    login(admin, users["SUPER_ADMIN"])
    response = admin.put(
        "/api/v1/roles/matrix/",
        {"role": "CANDIDATE", "capabilities": ["files.upload", "clients.view"]},
        format="json",
    )
    assert response.status_code == 200
    # Permission granted, but row scoping still returns nothing for candidates.
    listed = candidate.get("/api/v1/clients/")
    assert listed.status_code == 200
    assert listed.json()["count"] == 0


def test_super_admin_row_is_not_editable(users):
    admin = APIClient()
    login(admin, users["SUPER_ADMIN"])
    response = admin.put("/api/v1/roles/matrix/", {"role": "SUPER_ADMIN", "capabilities": []}, format="json")
    assert response.status_code == 409


def test_unknown_capability_is_rejected(users):
    admin = APIClient()
    login(admin, users["SUPER_ADMIN"])
    response = admin.put(
        "/api/v1/roles/matrix/", {"role": "CANDIDATE", "capabilities": ["nuke.all"]}, format="json"
    )
    assert response.status_code == 400


def test_lead_can_invite_externals_only(users, client_a):
    lead = APIClient()
    login(lead, users["ATLAS_LEAD"])
    ok = lead.post(
        "/api/v1/users/",
        {"email": "poc@clienta.test", "role": Role.CLIENT_USER, "client": str(client_a.public_id)},
        format="json",
    )
    assert ok.status_code == 201, ok.content
    denied = lead.post(
        "/api/v1/users/", {"email": "r2@test.local", "role": Role.ATLAS_RECRUITER}, format="json"
    )
    assert denied.status_code == 400
    escalate = lead.post(
        "/api/v1/users/", {"email": "sa@test.local", "role": Role.SUPER_ADMIN}, format="json"
    )
    assert escalate.status_code == 400


def test_client_user_requires_client(users):
    admin = APIClient()
    login(admin, users["SUPER_ADMIN"])
    response = admin.post("/api/v1/users/", {"email": "poc@x.test", "role": Role.CLIENT_USER}, format="json")
    assert response.status_code == 400
    assert "client" in response.json()["error"]["details"]


def test_cannot_demote_or_disable_self(users):
    admin = APIClient()
    login(admin, users["SUPER_ADMIN"])
    me = users["SUPER_ADMIN"].public_id
    assert admin.patch(f"/api/v1/users/{me}/", {"role": Role.CANDIDATE}, format="json").status_code == 400
    assert admin.patch(f"/api/v1/users/{me}/", {"is_active": False}, format="json").status_code == 400


def test_last_super_admin_is_protected(users, make_user):
    from apps.accounts.models import PermissionSet

    # A non-admin holding users.manage (via a custom set) cannot disable or demote a Super Admin.
    custom = PermissionSet.objects.create(
        code="user-managers", name="User managers", capabilities=["users.manage"]
    )
    manager = make_user(Role.ATLAS_RECRUITER, "manager@test.local")
    manager.permission_sets.add(custom)
    api = APIClient()
    login(api, manager)
    url = f"/api/v1/users/{users['SUPER_ADMIN'].public_id}/"
    assert api.patch(url, {"is_active": False}, format="json").status_code == 400
    assert api.patch(url, {"role": Role.CANDIDATE}, format="json").status_code == 400

    # A Super Admin can disable another Super Admin while one active admin remains.
    second = make_user(Role.SUPER_ADMIN, "admin2@test.local")
    admin = APIClient()
    login(admin, users["SUPER_ADMIN"])
    response = admin.patch(f"/api/v1/users/{second.public_id}/", {"is_active": False}, format="json")
    assert response.status_code == 200


def test_users_cannot_be_hard_deleted(users):
    admin = APIClient()
    login(admin, users["SUPER_ADMIN"])
    response = admin.delete(f"/api/v1/users/{users['CANDIDATE'].public_id}/")
    assert response.status_code == 405

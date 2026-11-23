import pytest
from rest_framework.test import APIClient

from apps.accounts.models import PermissionSet, Role, User
from apps.clients.models import Agency, Client

PASSWORD = "Very-Long-Test-Passw0rd!"


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def client_a(db):
    return Client.objects.create(name="Client A", code="CLA")


@pytest.fixture
def client_b(db):
    return Client.objects.create(name="Client B", code="CLB")


@pytest.fixture
def agency_a(db):
    return Agency.objects.create(name="Agency A", code="AGA")


@pytest.fixture
def agency_b(db):
    return Agency.objects.create(name="Agency B", code="AGB")


@pytest.fixture
def make_user(db):
    def _make(role=Role.CANDIDATE, email=None, password=PASSWORD, sets=(), **extra):
        email = email or f"{role.lower()}-{User.objects.count() + 1}@test.local"
        user = User.objects.create_user(email=email, password=password, role=role, **extra)
        for code in sets:
            user.permission_sets.add(PermissionSet.objects.get(code=code))
        return user

    return _make


@pytest.fixture
def users(make_user, client_a, agency_a):
    """One user per role (+ an Atlas Lead) used by the permission matrix tests."""
    return {
        "SUPER_ADMIN": make_user(Role.SUPER_ADMIN, "admin@test.local"),
        "ATLAS_LEAD": make_user(Role.ATLAS_RECRUITER, "lead@test.local", sets=["atlas_lead"]),
        "ATLAS_RECRUITER": make_user(Role.ATLAS_RECRUITER, "recruiter@test.local"),
        "CLIENT_USER": make_user(Role.CLIENT_USER, "client@test.local", client=client_a),
        "CONSULTANT": make_user(Role.CONSULTANT, "consultant@test.local", agency=agency_a),
        "CANDIDATE": make_user(Role.CANDIDATE, "candidate@test.local"),
    }


def login(api: APIClient, user, password=PASSWORD):
    response = api.post("/api/v1/auth/login/", {"email": user.email, "password": password}, format="json")
    assert response.status_code == 200, response.content
    return response


@pytest.fixture
def as_user(api):
    def _as(user):
        login(api, user)
        return api

    return _as

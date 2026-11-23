import pytest
from rest_framework.test import APIClient

from apps.audit.models import AuditLog

from .conftest import login

pytestmark = pytest.mark.django_db


def _as(user):
    api = APIClient()
    login(api, user)
    return api


def test_client_user_sees_only_own_client(users, client_a, client_b):
    api = _as(users["CLIENT_USER"])
    listed = api.get("/api/v1/clients/").json()
    assert [c["id"] for c in listed["results"]] == [str(client_a.public_id)]
    assert api.get(f"/api/v1/clients/{client_b.public_id}/").status_code == 404
    assert api.get(f"/api/v1/clients/{client_b.public_id}/contacts/").status_code == 404


def test_consultant_sees_only_own_agency(users, agency_a, agency_b):
    api = _as(users["CONSULTANT"])
    listed = api.get("/api/v1/agencies/").json()
    assert [a["id"] for a in listed["results"]] == [str(agency_a.public_id)]
    assert api.get(f"/api/v1/agencies/{agency_b.public_id}/").status_code == 404


def test_archived_clients_disappear(users, client_a):
    api = _as(users["SUPER_ADMIN"])
    assert api.delete(f"/api/v1/clients/{client_a.public_id}/").status_code == 204
    assert api.get(f"/api/v1/clients/{client_a.public_id}/").status_code == 404
    client_a.refresh_from_db()
    assert client_a.deleted_at is not None
    assert AuditLog.objects.filter(action="soft_delete", object_id=str(client_a.public_id)).exists()


def test_client_code_generated_and_contacts_crud(users):
    api = _as(users["SUPER_ADMIN"])
    created = api.post("/api/v1/clients/", {"name": "Acme Energy Services"}, format="json").json()
    assert created["code"] == "ACMEENER"
    contact = api.post(
        f"/api/v1/clients/{created['id']}/contacts/",
        {"name": "Pat Doe", "email": "pat@acme.test", "is_primary": True},
        format="json",
    )
    assert contact.status_code == 201
    detail = api.get(f"/api/v1/clients/{created['id']}/").json()
    assert detail["contacts"][0]["name"] == "Pat Doe"


def test_unknown_client_settings_rejected(users):
    api = _as(users["SUPER_ADMIN"])
    response = api.post("/api/v1/clients/", {"name": "X", "settings": {"hack": True}}, format="json")
    assert response.status_code == 400


def test_audit_records_field_diff_with_actor(users, client_a):
    admin = users["SUPER_ADMIN"]
    api = _as(admin)
    api.patch(f"/api/v1/clients/{client_a.public_id}/", {"city": "Gurugram"}, format="json")
    entry = AuditLog.objects.filter(action="update", object_id=str(client_a.public_id)).latest("at")
    assert entry.actor_id == admin.id
    assert entry.changes["city"] == {"from": "", "to": "Gurugram"}
    assert entry.request_id


def test_audit_never_stores_secrets(users):
    user = users["CANDIDATE"]
    user.set_password("Changed-Passw0rd-123!")
    user.save()
    for entry in AuditLog.objects.filter(object_id=str(user.public_id)):
        assert "pbkdf2" not in str(entry.changes)
        assert "md5$" not in str(entry.changes)


def test_audit_entries_are_immutable(users):
    entry = AuditLog.objects.first()
    entry.action = "tampered"
    with pytest.raises(RuntimeError):
        entry.save()
    with pytest.raises(RuntimeError):
        entry.delete()


def test_audit_api_filters(users):
    api = _as(users["SUPER_ADMIN"])
    response = api.get("/api/v1/audit/", {"action": "auth.login"})
    assert response.status_code == 200
    assert all(row["action"] == "auth.login" for row in response.json()["results"])

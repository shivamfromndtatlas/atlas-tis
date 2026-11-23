import hashlib
import io
import zipfile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.audit.models import AuditLog

from .conftest import login

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def _docx() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", "<w:document/>")
    return buf.getvalue()


def _as(user):
    api = APIClient()
    login(api, user)
    return api


def _upload(api, name, content, **extra):
    return api.post(
        "/api/v1/files/", {"file": SimpleUploadedFile(name, content), **extra}, format="multipart"
    )


def test_upload_pdf_and_docx(users, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    api = _as(users["ATLAS_RECRUITER"])
    pdf = _upload(api, "JD Dispatch.pdf", PDF, kind="jd")
    assert pdf.status_code == 201, pdf.content
    version = pdf.json()["versions"][0]
    assert version["sha256"] == hashlib.sha256(PDF).hexdigest()
    assert version["scan_status"] == "skipped"
    assert _upload(api, "resume.docx", _docx(), kind="resume").status_code == 201


@pytest.mark.parametrize(
    ("name", "content", "code"),
    [
        ("evil.exe", b"MZ\x90\x00", "FILE_TYPE_NOT_ALLOWED"),
        ("fake.pdf", b"MZ\x90\x00 not a pdf", "FILE_CONTENT_MISMATCH"),
        ("fake.docx", b"PK\x03\x04garbage", "FILE_CONTENT_MISMATCH"),
        ("empty.pdf", b"", "FILE_EMPTY"),
    ],
)
def test_rejected_uploads(users, settings, tmp_path, name, content, code):
    settings.MEDIA_ROOT = tmp_path
    api = _as(users["ATLAS_RECRUITER"])
    response = _upload(api, name, content)
    assert response.status_code in (400, 422)
    if response.status_code == 422:
        assert response.json()["error"]["code"] == code


def test_size_limit(users, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.FILE_MAX_BYTES = {"resume": 10, "default": 10}
    api = _as(users["CANDIDATE"])
    response = _upload(api, "cv.pdf", PDF, kind="resume")
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_new_version_and_signed_download(users, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    api = _as(users["ATLAS_RECRUITER"])
    doc = _upload(api, "jd.pdf", PDF, kind="jd").json()
    v2 = _upload(api, "jd-v2.pdf", PDF + b"%v2", document=doc["id"]).json()
    assert v2["current_version"] == 2 and len(v2["versions"]) == 2

    link = api.post(f"/api/v1/files/{doc['id']}/download-link/").json()["url"]
    anonymous = APIClient()
    response = anonymous.get(link)
    assert response.status_code == 200
    assert b"".join(response.streaming_content) == PDF + b"%v2"
    assert AuditLog.objects.filter(action="file.download", object_id=doc["id"]).exists()
    assert anonymous.get(link.replace("/download/", "/download/x")).status_code == 410


def test_client_user_sees_own_client_documents_only(users, client_a, client_b, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    recruiter = _as(users["ATLAS_RECRUITER"])
    mine = _upload(recruiter, "a.pdf", PDF, owner_type="client", owner_id=str(client_a.public_id)).json()
    other = _upload(recruiter, "b.pdf", PDF, owner_type="client", owner_id=str(client_b.public_id)).json()

    client_user = _as(users["CLIENT_USER"])
    ids = [d["id"] for d in client_user.get("/api/v1/files/").json()["results"]]
    assert mine["id"] in ids and other["id"] not in ids
    assert client_user.post(f"/api/v1/files/{other['id']}/download-link/").status_code == 404
    # cannot attach files to another client's record
    denied = _upload(client_user, "c.pdf", PDF, owner_type="client", owner_id=str(client_b.public_id))
    assert denied.status_code == 404


def test_candidate_sees_only_own_uploads(users, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    candidate = _as(users["CANDIDATE"])
    _upload(candidate, "cv.pdf", PDF, kind="resume")
    recruiter = _as(users["ATLAS_RECRUITER"])
    _upload(recruiter, "jd.pdf", PDF, kind="jd")
    assert candidate.get("/api/v1/files/").json()["count"] == 1

"""Upload validation: extension allow-list, magic-byte sniffing, size limits, hashing, AV scanning."""

from __future__ import annotations

import hashlib
import socket
import struct
import zipfile

from django.conf import settings

ALLOWED = {
    # ext: (mime, magic check)
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "doc": "application/msword",
    "txt": "text/plain",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
}


class UploadRejected(Exception):
    def __init__(self, message: str, code: str = "UPLOAD_REJECTED"):
        super().__init__(message)
        self.code = code


def _matches(ext: str, head: bytes, fileobj) -> bool:
    if ext == "pdf":
        return head.startswith(b"%PDF-")
    if ext == "doc":
        return head.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    if ext == "docx":
        if not head.startswith(b"PK\x03\x04"):
            return False
        fileobj.seek(0)
        try:
            with zipfile.ZipFile(fileobj) as zf:
                return "word/document.xml" in zf.namelist()
        except zipfile.BadZipFile:
            return False
        finally:
            fileobj.seek(0)
    if ext == "png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if ext in ("jpg", "jpeg"):
        return head.startswith(b"\xff\xd8\xff")
    if ext == "txt":
        try:
            head.decode("utf-8")
        except UnicodeDecodeError:
            return False
        return b"\x00" not in head
    return False


def validate_upload(uploaded, kind: str) -> tuple[str, str]:
    """Returns (mime, sha256). Raises UploadRejected."""
    name = uploaded.name or ""
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED:
        raise UploadRejected(f"File type .{ext or '?'} is not allowed.", "FILE_TYPE_NOT_ALLOWED")
    limit = settings.FILE_MAX_BYTES.get(kind, settings.FILE_MAX_BYTES["default"])
    if uploaded.size > limit:
        raise UploadRejected(f"File is larger than {limit // (1024 * 1024)} MB.", "FILE_TOO_LARGE")
    if uploaded.size == 0:
        raise UploadRejected("File is empty.", "FILE_EMPTY")

    uploaded.seek(0)
    head = uploaded.read(4096)
    uploaded.seek(0)
    if not _matches(ext, head, uploaded):
        raise UploadRejected("File content does not match its extension.", "FILE_CONTENT_MISMATCH")

    digest = hashlib.sha256()
    for chunk in uploaded.chunks():
        digest.update(chunk)
    uploaded.seek(0)
    return ALLOWED[ext], digest.hexdigest()


def scan(uploaded) -> tuple[str, str]:
    """Returns (scan_status, detail). Uses clamd INSTREAM when FILE_SCANNER=clamav."""
    if settings.FILE_SCANNER != "clamav":
        return "skipped", ""
    try:
        with socket.create_connection((settings.CLAMAV_HOST, settings.CLAMAV_PORT), timeout=30) as sock:
            sock.sendall(b"zINSTREAM\0")
            uploaded.seek(0)
            for chunk in uploaded.chunks(64 * 1024):
                sock.sendall(struct.pack("!L", len(chunk)) + chunk)
            sock.sendall(struct.pack("!L", 0))
            reply = sock.recv(4096).decode("utf-8", "replace").strip("\0 \n")
        uploaded.seek(0)
    except OSError as exc:
        return "error", f"scanner unavailable: {exc}"[:255]
    if reply.endswith("OK"):
        return "clean", ""
    if "FOUND" in reply:
        return "infected", reply[:255]
    return "error", reply[:255]

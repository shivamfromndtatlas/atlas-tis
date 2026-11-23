import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel


def version_upload_to(instance, filename: str) -> str:
    # Never trust the uploaded filename for storage paths.
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"documents/{instance.document.public_id}/{uuid.uuid4().hex}.{ext}"


class DocumentQuerySet(models.QuerySet):
    def for_user(self, user):
        """Row scoping: org-wide viewers, the uploader, or a client user for their client's documents."""
        if not user.is_authenticated:
            return self.none()
        qs = self.filter(archived_at__isnull=True)
        if user.has_capability("files.view_all"):
            return qs
        visible = Q(created_by=user)
        if user.role == "CLIENT_USER" and user.client_id:
            visible |= Q(owner_type="client", owner_id=str(user.client.public_id))
        return qs.filter(visible)


class Document(TimeStampedModel):
    """A logical document with retained versions (resume, JD, success profile, offer letter...)."""

    class Kind(models.TextChoices):
        RESUME = "resume", "Resume"
        JD = "jd", "Job description"
        SUCCESS_PROFILE = "success_profile", "Success profile"
        OFFER_LETTER = "offer_letter", "Offer letter"
        CONTRACT = "contract", "Contract"
        OTHER = "other", "Other"

    kind = models.CharField(max_length=32, choices=Kind.choices, default=Kind.OTHER, db_index=True)
    title = models.CharField(max_length=255)
    # Generic owner by public id, e.g. ("client", "<uuid>"); typed links come with jobs/candidates.
    owner_type = models.CharField(max_length=32, blank=True, db_index=True)
    owner_id = models.CharField(max_length=64, blank=True, db_index=True)
    current_version = models.PositiveIntegerField(default=0)
    archived_at = models.DateTimeField(null=True, blank=True)

    objects = DocumentQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["owner_type", "owner_id"])]

    def __str__(self) -> str:
        return self.title


class DocumentVersion(models.Model):
    class ScanStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        CLEAN = "clean", "Clean"
        INFECTED = "infected", "Infected"
        SKIPPED = "skipped", "Not scanned (scanner disabled)"
        ERROR = "error", "Scan error"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="versions")
    version = models.PositiveIntegerField()
    original_name = models.CharField(max_length=255)
    mime = models.CharField(max_length=127)
    size = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64, db_index=True)
    file = models.FileField(upload_to=version_upload_to, max_length=255)
    scan_status = models.CharField(max_length=16, choices=ScanStatus.choices, default=ScanStatus.PENDING)
    scan_detail = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["-version"]
        constraints = [models.UniqueConstraint(fields=["document", "version"], name="uniq_document_version")]

    def __str__(self) -> str:
        return f"{self.document} v{self.version}"

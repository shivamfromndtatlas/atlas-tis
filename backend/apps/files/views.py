from django.conf import settings
from django.core import signing
from django.db import transaction
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import record as audit
from apps.clients.models import Client
from apps.core.exceptions import TISError
from apps.core.permissions import HasCapability

from .models import Document, DocumentVersion
from .validation import UploadRejected, scan, validate_upload

DOWNLOAD_SALT = "tis.file-download"
OWNER_TYPES = {"client": Client}


class DocumentVersionSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    uploaded_by = serializers.CharField(source="created_by.email", read_only=True, default=None)

    class Meta:
        model = DocumentVersion
        fields = [
            "id",
            "version",
            "original_name",
            "mime",
            "size",
            "sha256",
            "scan_status",
            "created_at",
            "uploaded_by",
        ]


class DocumentSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    versions = DocumentVersionSerializer(many=True, read_only=True)

    class Meta:
        model = Document
        fields = [
            "id",
            "kind",
            "title",
            "owner_type",
            "owner_id",
            "current_version",
            "versions",
            "created_at",
        ]


class UploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    kind = serializers.ChoiceField(choices=Document.Kind.choices, default=Document.Kind.OTHER)
    title = serializers.CharField(required=False, allow_blank=True, max_length=255)
    owner_type = serializers.ChoiceField(choices=sorted(OWNER_TYPES), required=False, allow_blank=True)
    owner_id = serializers.UUIDField(required=False, allow_null=True)
    document = serializers.UUIDField(
        required=False, allow_null=True, help_text="Add a new version to this document"
    )


class DocumentViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet
):
    serializer_class = DocumentSerializer
    permission_classes = [HasCapability]
    capability_map = {
        "list": None,
        "retrieve": None,
        "download_link": None,
        "create": "files.upload",
        "destroy": "files.upload",
    }
    parser_classes = [MultiPartParser, FormParser]
    lookup_field = "public_id"
    lookup_url_kwarg = "id"
    filterset_fields = ["kind", "owner_type", "owner_id"]

    def get_queryset(self):
        return Document.objects.for_user(self.request.user).prefetch_related("versions__created_by")

    def _check_owner(self, owner_type, owner_id):
        if not owner_type:
            return
        model = OWNER_TYPES[owner_type]
        scoped = model.objects.for_user(self.request.user)
        if not scoped.filter(public_id=owner_id).exists():
            raise TISError(
                "You cannot attach documents to this record.", code="OWNER_NOT_FOUND", status_code=404
            )

    @extend_schema(request={"multipart/form-data": UploadSerializer}, responses={201: DocumentSerializer})
    @transaction.atomic
    def create(self, request):
        data = UploadSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        uploaded = v["file"]
        try:
            mime, sha256 = validate_upload(uploaded, v["kind"])
        except UploadRejected as exc:
            raise TISError(str(exc), code=exc.code, status_code=422) from exc
        scan_status, scan_detail = scan(uploaded)
        if scan_status == "infected":
            audit("file.rejected_infected", None, {"name": uploaded.name, "detail": scan_detail})
            raise TISError("The file failed the virus scan.", code="FILE_INFECTED", status_code=422)

        if v.get("document"):
            document = get_object_or_404(self.get_queryset().select_for_update(), public_id=v["document"])
        else:
            owner_type = v.get("owner_type") or ""
            owner_id = str(v["owner_id"]) if v.get("owner_id") else ""
            if bool(owner_type) != bool(owner_id):
                raise TISError("owner_type and owner_id go together.", code="OWNER_INCOMPLETE")
            self._check_owner(owner_type, owner_id)
            document = Document.objects.create(
                kind=v["kind"],
                title=v.get("title") or uploaded.name,
                owner_type=owner_type,
                owner_id=owner_id,
                created_by=request.user,
                updated_by=request.user,
            )
        document.current_version += 1
        document.updated_by = request.user
        document.save(update_fields=["current_version", "updated_by", "updated_at"])
        DocumentVersion.objects.create(
            document=document,
            version=document.current_version,
            original_name=uploaded.name[:255],
            mime=mime,
            size=uploaded.size,
            sha256=sha256,
            file=uploaded,
            scan_status=scan_status,
            scan_detail=scan_detail,
            created_by=request.user,
        )
        document = self.get_queryset().get(pk=document.pk)
        return Response(DocumentSerializer(document).data, status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance):
        if instance.created_by_id != self.request.user.id and not self.request.user.has_capability(
            "files.view_all"
        ):
            raise TISError("Only the uploader can archive this document.", code="FORBIDDEN", status_code=403)
        instance.archived_at = timezone.now()
        instance.updated_by = self.request.user
        instance.save(update_fields=["archived_at", "updated_by", "updated_at"])

    @extend_schema(request=None, responses={200: OpenApiResponse(description="{url, expires_in}")})
    @action(detail=True, methods=["post"], url_path="download-link")
    def download_link(self, request, id=None):
        document = self.get_object()
        version_no = int(request.query_params.get("version") or document.current_version)
        version = get_object_or_404(document.versions, version=version_no)
        if version.scan_status in ("infected", "pending"):
            raise TISError(
                "This file is not available for download.", code="FILE_UNAVAILABLE", status_code=409
            )
        token = signing.dumps({"v": str(version.public_id), "u": request.user.pk}, salt=DOWNLOAD_SALT)
        url = request.build_absolute_uri(reverse("file-download", kwargs={"token": token}))
        return Response({"url": url, "expires_in": settings.FILE_DOWNLOAD_TOKEN_TTL_SECONDS})


class DownloadView(APIView):
    """Short-lived signed link (issued after a permission check); logged on every use."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(responses={200: OpenApiResponse(description="File bytes")})
    def get(self, request, token: str):
        try:
            data = signing.loads(token, salt=DOWNLOAD_SALT, max_age=settings.FILE_DOWNLOAD_TOKEN_TTL_SECONDS)
        except signing.BadSignature as exc:
            raise TISError("Download link expired.", code="LINK_EXPIRED", status_code=410) from exc
        version = get_object_or_404(DocumentVersion.objects.select_related("document"), public_id=data["v"])
        from apps.accounts.models import User

        actor = User.objects.filter(pk=data["u"], is_active=True).first()
        if actor is None:
            raise TISError("Download link expired.", code="LINK_EXPIRED", status_code=410)
        audit("file.download", version.document, {"version": version.version}, actor=actor)
        return FileResponse(
            version.file.open("rb"),
            as_attachment=True,
            filename=version.original_name,
            content_type=version.mime,
        )

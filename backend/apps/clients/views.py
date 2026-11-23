from django.shortcuts import get_object_or_404
from rest_framework import viewsets

from apps.core.permissions import HasCapability

from .models import Agency, Client, ClientContact
from .serializers import AgencySerializer, ClientContactSerializer, ClientListSerializer, ClientSerializer


class AuthorshipMixin:
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class ClientViewSet(AuthorshipMixin, viewsets.ModelViewSet):
    """Client companies (spec M2). DELETE archives (soft delete)."""

    permission_classes = [HasCapability]
    capability_map = {"list": "clients.view", "retrieve": "clients.view", "*": "clients.manage"}
    lookup_field = "public_id"
    lookup_url_kwarg = "id"
    filterset_fields = ["status", "is_internal"]
    search_fields = ["name", "legal_name", "code", "city"]
    ordering_fields = ["name", "created_at", "status"]

    def get_queryset(self):
        return (
            Client.objects.for_user(self.request.user)
            .select_related("account_owner")
            .prefetch_related("contacts")
        )

    def get_serializer_class(self):
        return ClientListSerializer if self.action == "list" else ClientSerializer

    def perform_destroy(self, instance):
        instance.updated_by = self.request.user
        instance.soft_delete()


class ClientContactViewSet(AuthorshipMixin, viewsets.ModelViewSet):
    serializer_class = ClientContactSerializer
    permission_classes = [HasCapability]
    capability_map = {"list": "clients.view", "retrieve": "clients.view", "*": "clients.manage"}
    lookup_field = "public_id"
    lookup_url_kwarg = "id"

    def get_client(self):
        return get_object_or_404(
            Client.objects.for_user(self.request.user), public_id=self.kwargs["client_id"]
        )

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ClientContact.objects.none()
        return ClientContact.objects.filter(client=self.get_client())

    def perform_create(self, serializer):
        serializer.save(client=self.get_client(), created_by=self.request.user, updated_by=self.request.user)


class AgencyViewSet(AuthorshipMixin, viewsets.ModelViewSet):
    serializer_class = AgencySerializer
    permission_classes = [HasCapability]
    capability_map = {"list": "agencies.view", "retrieve": "agencies.view", "*": "agencies.manage"}
    lookup_field = "public_id"
    lookup_url_kwarg = "id"
    filterset_fields = ["status", "agency_type"]
    search_fields = ["name", "code", "contact_name"]
    ordering_fields = ["name", "created_at"]

    def get_queryset(self):
        return Agency.objects.for_user(self.request.user).select_related("account_lead")

    def perform_destroy(self, instance):
        instance.updated_by = self.request.user
        instance.soft_delete()

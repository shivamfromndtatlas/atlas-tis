import django_filters
from rest_framework import serializers, viewsets

from apps.core.permissions import HasCapability

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = [
            "id",
            "at",
            "actor_label",
            "actor_role",
            "ip",
            "request_id",
            "action",
            "object_type",
            "object_id",
            "object_repr",
            "changes",
            "source",
        ]


class AuditFilter(django_filters.FilterSet):
    since = django_filters.IsoDateTimeFilter(field_name="at", lookup_expr="gte")
    until = django_filters.IsoDateTimeFilter(field_name="at", lookup_expr="lte")
    actor = django_filters.CharFilter(field_name="actor_label", lookup_expr="icontains")

    class Meta:
        model = AuditLog
        fields = ["action", "object_type", "object_id", "since", "until", "actor"]


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [HasCapability]
    capability_map = {"*": "audit.view"}
    filterset_class = AuditFilter
    search_fields = ["object_repr", "actor_label", "action"]
    ordering_fields = ["at"]

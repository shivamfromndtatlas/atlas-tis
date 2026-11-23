import re

from rest_framework import serializers

from apps.accounts.models import User

from .models import Agency, Client, ClientContact

ATLAS_STAFF = ["SUPER_ADMIN", "ATLAS_RECRUITER"]
CLIENT_SETTINGS = {"client_can_publish", "client_approves_offers", "client_can_invite_colleagues"}


def generate_code(model, name: str) -> str:
    base = re.sub(r"[^A-Z0-9]", "", name.upper())[:8] or "C"
    code, n = base, 1
    while model.objects.filter(code=code).exists():
        n += 1
        code = f"{base}{n}"
    return code


def _unique_code(model, value, instance):
    value = (value or "").strip().upper()
    if value:
        qs = model.objects.filter(code=value)
        if instance:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            raise serializers.ValidationError("This code is already in use.")
    return value


class ClientContactSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    user = serializers.SlugRelatedField(
        slug_field="public_id", queryset=User.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = ClientContact
        fields = ["id", "name", "designation", "email", "phone", "is_primary", "user", "created_at"]
        read_only_fields = ["created_at"]


class ClientSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    code = serializers.CharField(required=False, allow_blank=True, max_length=24)
    account_owner = serializers.SlugRelatedField(
        slug_field="public_id",
        queryset=User.objects.filter(role__in=ATLAS_STAFF, is_active=True),
        required=False,
        allow_null=True,
    )
    account_owner_name = serializers.CharField(source="account_owner.full_name", read_only=True, default=None)
    user_count = serializers.SerializerMethodField()
    contacts = ClientContactSerializer(many=True, read_only=True)

    class Meta:
        model = Client
        fields = [
            "id",
            "name",
            "legal_name",
            "code",
            "industry",
            "is_internal",
            "status",
            "website",
            "email",
            "phone",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "country",
            "postal_code",
            "tax_id",
            "notes",
            "account_owner",
            "account_owner_name",
            "settings",
            "user_count",
            "contacts",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_user_count(self, obj) -> int:
        return obj.users.filter(is_active=True).count()

    def validate_code(self, value):
        return _unique_code(Client, value, self.instance)

    def validate_settings(self, value):
        unknown = set(value) - CLIENT_SETTINGS
        if unknown:
            raise serializers.ValidationError(f"Unknown settings: {', '.join(sorted(unknown))}")
        return value

    def create(self, validated):
        if not validated.get("code"):
            validated["code"] = generate_code(Client, validated["name"])
        return super().create(validated)


class ClientListSerializer(ClientSerializer):
    class Meta(ClientSerializer.Meta):
        fields = [f for f in ClientSerializer.Meta.fields if f not in ("contacts", "notes", "settings")]


class AgencySerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    code = serializers.CharField(required=False, allow_blank=True, max_length=24)
    account_lead = serializers.SlugRelatedField(
        slug_field="public_id",
        queryset=User.objects.filter(role__in=ATLAS_STAFF, is_active=True),
        required=False,
        allow_null=True,
    )
    account_lead_name = serializers.CharField(source="account_lead.full_name", read_only=True, default=None)
    consultant_count = serializers.SerializerMethodField()

    class Meta:
        model = Agency
        fields = [
            "id",
            "name",
            "code",
            "agency_type",
            "status",
            "contact_name",
            "contact_email",
            "contact_phone",
            "commercial_terms",
            "sla_notes",
            "account_lead",
            "account_lead_name",
            "consultant_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_consultant_count(self, obj) -> int:
        return obj.users.filter(is_active=True).count()

    def validate_code(self, value):
        return _unique_code(Agency, value, self.instance)

    def create(self, validated):
        if not validated.get("code"):
            validated["code"] = generate_code(Agency, validated["name"])
        return super().create(validated)

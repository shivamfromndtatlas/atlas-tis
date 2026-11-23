from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from apps.clients.models import Agency, Client

from .capabilities import CAPABILITIES, CAPABILITY_CODES
from .models import EXTERNAL_ROLES, PermissionSet, Role, User


class PermissionSetBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = PermissionSet
        fields = ["id", "code", "name"]


class MeSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    full_name = serializers.CharField(read_only=True)
    capabilities = serializers.SerializerMethodField()
    permission_sets = PermissionSetBriefSerializer(many=True, read_only=True)
    client = serializers.SerializerMethodField()
    agency = serializers.SerializerMethodField()
    mfa_required = serializers.BooleanField(read_only=True)
    mfa_setup_required = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "mobile_e164",
            "first_name",
            "last_name",
            "full_name",
            "role",
            "timezone",
            "client",
            "agency",
            "permission_sets",
            "capabilities",
            "mfa_enabled",
            "mfa_required",
            "mfa_setup_required",
            "email_verified_at",
            "last_login",
        ]
        read_only_fields = ["email", "role", "mfa_enabled", "email_verified_at", "last_login"]

    def get_capabilities(self, obj) -> list[str]:
        return sorted(obj.capabilities)

    def get_client(self, obj) -> dict | None:
        return {"id": str(obj.client.public_id), "name": obj.client.name} if obj.client_id else None

    def get_agency(self, obj) -> dict | None:
        return {"id": str(obj.agency.public_id), "name": obj.agency.name} if obj.agency_id else None

    def get_mfa_setup_required(self, obj) -> bool:
        return obj.mfa_required and not obj.mfa_enabled


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False)


class OTPRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class OTPVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.RegexField(r"^\d{4,8}$")


class MFAVerifySerializer(serializers.Serializer):
    challenge = serializers.CharField()
    code = serializers.RegexField(r"^\d{6}$")


class MFACodeSerializer(serializers.Serializer):
    code = serializers.RegexField(r"^\d{6}$")


class MFADisableSerializer(MFACodeSerializer):
    password = serializers.CharField(trim_whitespace=False)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordSetSerializer(serializers.Serializer):
    uid = serializers.UUIDField()
    token = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False)


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(trim_whitespace=False)
    new_password = serializers.CharField(trim_whitespace=False)

    def validate(self, attrs):
        user = self.context["request"].user
        if not user.check_password(attrs["current_password"]):
            raise serializers.ValidationError({"current_password": "Incorrect password."})
        validate_password(attrs["new_password"], user)
        return attrs


# --- User administration ----------------------------------------------------------
class UserAdminSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    full_name = serializers.CharField(read_only=True)
    client = serializers.SlugRelatedField(
        slug_field="public_id", queryset=Client.objects.alive(), required=False, allow_null=True
    )
    client_name = serializers.CharField(source="client.name", read_only=True, default=None)
    agency = serializers.SlugRelatedField(
        slug_field="public_id", queryset=Agency.objects.alive(), required=False, allow_null=True
    )
    agency_name = serializers.CharField(source="agency.name", read_only=True, default=None)
    permission_sets = serializers.SlugRelatedField(
        slug_field="code",
        many=True,
        required=False,
        queryset=PermissionSet.objects.filter(role_default__isnull=True),
    )
    invite_pending = serializers.SerializerMethodField()
    send_invite = serializers.BooleanField(write_only=True, required=False, default=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "mobile_e164",
            "role",
            "client",
            "client_name",
            "agency",
            "agency_name",
            "permission_sets",
            "is_active",
            "mfa_enabled",
            "invite_pending",
            "last_login",
            "date_joined",
            "send_invite",
        ]
        read_only_fields = ["mfa_enabled", "last_login", "date_joined"]

    def get_invite_pending(self, obj) -> bool:
        return obj.invite_accepted_at is None and not obj.has_usable_password()

    def validate_email(self, value):
        value = value.strip().lower()
        qs = User.objects.filter(email=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate(self, attrs):
        actor = self.context["request"].user
        role = attrs.get("role", getattr(self.instance, "role", None))
        client = attrs.get("client", getattr(self.instance, "client", None))
        agency = attrs.get("agency", getattr(self.instance, "agency", None))

        if role == Role.CLIENT_USER and client is None:
            raise serializers.ValidationError({"client": "Client users must belong to a client."})
        if role != Role.CLIENT_USER and client is not None:
            attrs["client"] = None
        if role != Role.CONSULTANT and agency is not None:
            attrs["agency"] = None

        # Actors with only users.invite_external may manage CLIENT_USER / CONSULTANT accounts only.
        if not actor.has_capability("users.manage"):
            current_role = getattr(self.instance, "role", None)
            if role not in EXTERNAL_ROLES or (current_role and current_role not in EXTERNAL_ROLES):
                raise serializers.ValidationError(
                    {"role": "You can only manage client users and consultants."}
                )
            if "permission_sets" in attrs:
                raise serializers.ValidationError({"permission_sets": "You cannot assign permission sets."})
        if role == Role.SUPER_ADMIN and actor.role != Role.SUPER_ADMIN:
            raise serializers.ValidationError({"role": "Only a Super Admin can grant Super Admin."})

        # Protect against locking the organisation out (AtlasHiring rule kept).
        if self.instance is not None:
            demoting = self.instance.role == Role.SUPER_ADMIN and role != Role.SUPER_ADMIN
            disabling = self.instance.is_active and attrs.get("is_active") is False
            if (demoting or disabling) and self.instance.pk == actor.pk:
                raise serializers.ValidationError("You cannot demote or disable your own account.")
            if demoting or (disabling and self.instance.role == Role.SUPER_ADMIN):
                others = User.objects.filter(role=Role.SUPER_ADMIN, is_active=True).exclude(
                    pk=self.instance.pk
                )
                if not others.exists():
                    raise serializers.ValidationError("At least one active Super Admin is required.")
        return attrs

    @transaction.atomic
    def create(self, validated):
        from .services import send_invite

        sets = validated.pop("permission_sets", [])
        invite = validated.pop("send_invite", True)
        user = User.objects.create_user(invited_by=self.context["request"].user, **validated)
        if sets:
            user.permission_sets.set(sets)
        if invite:
            transaction.on_commit(lambda: send_invite(user, self.context["request"].user))
        return user

    @transaction.atomic
    def update(self, instance, validated):
        validated.pop("send_invite", None)
        sets = validated.pop("permission_sets", None)
        security_change = any(
            k in validated and validated[k] != getattr(instance, k)
            for k in ("role", "is_active", "client", "agency")
        )
        for key, value in validated.items():
            setattr(instance, key, value)
        if sets is not None and set(sets) != set(instance.permission_sets.all()):
            instance.permission_sets.set(sets)
            security_change = True
        if security_change:
            instance.revoke_tokens()
        instance.save()
        return instance


class PermissionSetSerializer(serializers.ModelSerializer):
    user_count = serializers.IntegerField(read_only=True, source="users.count")

    class Meta:
        model = PermissionSet
        fields = [
            "id",
            "code",
            "name",
            "description",
            "capabilities",
            "is_system",
            "role_default",
            "user_count",
        ]
        read_only_fields = ["is_system", "role_default"]

    def validate_capabilities(self, value):
        unknown = set(value) - CAPABILITY_CODES
        if unknown:
            raise serializers.ValidationError(f"Unknown capabilities: {', '.join(sorted(unknown))}")
        return sorted(set(value))


class CapabilitySerializer(serializers.Serializer):
    code = serializers.CharField()
    group = serializers.CharField()
    label = serializers.CharField()
    description = serializers.CharField()


class RoleMatrixRowSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=Role.choices)
    label = serializers.CharField(read_only=True)
    capabilities = serializers.ListField(child=serializers.CharField())
    editable = serializers.BooleanField(read_only=True)

    def validate_capabilities(self, value):
        unknown = set(value) - CAPABILITY_CODES
        if unknown:
            raise serializers.ValidationError(f"Unknown capabilities: {', '.join(sorted(unknown))}")
        return sorted(set(value))


def all_capabilities() -> list[dict]:
    return [c.__dict__ for c in CAPABILITIES]

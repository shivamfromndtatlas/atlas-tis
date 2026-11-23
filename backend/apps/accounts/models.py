import uuid

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel

from .capabilities import CAPABILITY_CODES, MFA_REQUIRED_ROLES, MFA_REQUIRED_SETS


class Role(models.TextChoices):
    SUPER_ADMIN = "SUPER_ADMIN", "Super Admin"
    ATLAS_RECRUITER = "ATLAS_RECRUITER", "Atlas Recruiter"
    CLIENT_USER = "CLIENT_USER", "Client Recruiter / POC"
    CONSULTANT = "CONSULTANT", "Consultant"
    CANDIDATE = "CANDIDATE", "Candidate"


STAFF_ROLES = {Role.SUPER_ADMIN, Role.ATLAS_RECRUITER}
EXTERNAL_ROLES = {Role.CLIENT_USER, Role.CONSULTANT}


class PermissionSet(TimeStampedModel):
    """A named bundle of capabilities.

    System sets with ``role_default`` hold each role's default capabilities (the matrix).
    Other sets are add-ons (e.g. Atlas Lead) or custom roles created by a Super Admin.
    """

    code = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    capabilities = models.JSONField(default=list)
    is_system = models.BooleanField(default=False)
    role_default = models.CharField(max_length=32, choices=Role.choices, null=True, blank=True, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        self.capabilities = sorted(set(self.capabilities) & CAPABILITY_CODES)
        super().save(*args, **kwargs)


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create(self, email, password, **extra):
        if not email:
            raise ValueError("Email is required")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("role", Role.CANDIDATE)
        return self._create(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.update(role=Role.SUPER_ADMIN, is_staff=True, is_superuser=True)
        return self._create(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    email = models.EmailField(unique=True)
    mobile_e164 = models.CharField(max_length=20, unique=True, null=True, blank=True)
    first_name = models.CharField(max_length=80, blank=True)
    last_name = models.CharField(max_length=80, blank=True)
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.CANDIDATE, db_index=True)
    client = models.ForeignKey(
        "clients.Client", null=True, blank=True, on_delete=models.PROTECT, related_name="users"
    )
    agency = models.ForeignKey(
        "clients.Agency", null=True, blank=True, on_delete=models.PROTECT, related_name="users"
    )
    permission_sets = models.ManyToManyField(PermissionSet, blank=True, related_name="users")

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False, help_text="Django admin access only (dev).")
    date_joined = models.DateTimeField(default=timezone.now)
    invited_by = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    invite_accepted_at = models.DateTimeField(null=True, blank=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    mobile_verified_at = models.DateTimeField(null=True, blank=True)
    timezone = models.CharField(max_length=64, default="Asia/Kolkata")

    mfa_enabled = models.BooleanField(default=False)
    mfa_secret = models.CharField(max_length=64, blank=True)  # TODO(S15): encrypt at rest (KMS/Fernet)
    # Bumped on role change, deactivation, password reset and MFA reset: invalidates every issued token.
    token_version = models.PositiveIntegerField(default=1)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        ordering = ["email"]
        indexes = [models.Index(fields=["role", "is_active"])]

    def __str__(self) -> str:
        return self.email

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip() or self.email

    # -- capabilities ---------------------------------------------------------
    @property
    def capabilities(self) -> frozenset[str]:
        cached = getattr(self, "_capabilities_cache", None)
        if cached is not None:
            return cached
        if not self.is_active:
            caps: frozenset[str] = frozenset()
        elif self.role == Role.SUPER_ADMIN:
            caps = CAPABILITY_CODES
        else:
            sets = PermissionSet.objects.filter(
                models.Q(role_default=self.role) | models.Q(users=self)
            ).distinct()
            caps = frozenset(c for s in sets for c in s.capabilities) & CAPABILITY_CODES
        self._capabilities_cache = caps
        return caps

    def has_capability(self, code: str) -> bool:
        return code in self.capabilities

    @property
    def mfa_required(self) -> bool:
        if self.role in MFA_REQUIRED_ROLES:
            return True
        return self.permission_sets.filter(code__in=MFA_REQUIRED_SETS).exists()

    def revoke_tokens(self) -> None:
        """Invalidate every access/refresh token issued so far (caller saves)."""
        self.token_version += 1
        self._capabilities_cache = None


class OTPChallenge(models.Model):
    class Purpose(models.TextChoices):
        LOGIN = "login", "Login"
        VERIFY_EMAIL = "verify_email", "Verify email"

    target = models.CharField(max_length=254, db_index=True)
    channel = models.CharField(max_length=16, default="email")
    purpose = models.CharField(max_length=32, choices=Purpose.choices)
    code_hash = models.CharField(max_length=128)
    attempts = models.PositiveSmallIntegerField(default=0)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["target", "purpose", "created_at"])]

    def __str__(self) -> str:
        return f"OTP {self.purpose} for {self.target}"

    @property
    def is_usable(self) -> bool:
        return (
            self.consumed_at is None
            and self.expires_at > timezone.now()
            and self.attempts < settings.OTP_MAX_ATTEMPTS
        )

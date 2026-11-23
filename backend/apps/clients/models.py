from django.conf import settings
from django.db import models

from apps.core.models import SoftDeleteModel, SoftDeleteQuerySet, TimeStampedModel


class ClientQuerySet(SoftDeleteQuerySet):
    def for_user(self, user):
        """Row scoping (spec section 3.3)."""
        qs = self.alive()
        if not user.is_authenticated or not user.has_capability("clients.view"):
            return qs.none()
        if user.role == "CLIENT_USER":
            return qs.filter(pk=user.client_id) if user.client_id else qs.none()
        if user.role in ("SUPER_ADMIN", "ATLAS_RECRUITER"):
            return qs
        return qs.none()


class Client(TimeStampedModel, SoftDeleteModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PROSPECT = "prospect", "Prospect"
        INACTIVE = "inactive", "Inactive"

    name = models.CharField(max_length=200)
    legal_name = models.CharField(max_length=255, blank=True)
    code = models.CharField(max_length=24, unique=True)
    industry = models.CharField(max_length=120, blank=True)
    is_internal = models.BooleanField(
        default=False, help_text="NDT Atlas's own hiring is modelled as an internal client."
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    website = models.URLField(blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120, blank=True)
    state = models.CharField(max_length=120, blank=True)
    country = models.CharField(max_length=120, blank=True, default="India")
    postal_code = models.CharField(max_length=20, blank=True)
    tax_id = models.CharField(max_length=40, blank=True, help_text="GSTIN / EIN (optional)")
    notes = models.TextField(blank=True)
    account_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="owned_clients",
    )
    # Per-client flags from spec section 22 (D1, D3): client_can_publish, client_approves_offers.
    settings = models.JSONField(default=dict, blank=True)

    objects = ClientQuerySet.as_manager()

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class ClientContact(TimeStampedModel):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="contacts")
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="client_contact",
    )
    name = models.CharField(max_length=160)
    designation = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ["-is_primary", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.client})"


class AgencyQuerySet(SoftDeleteQuerySet):
    def for_user(self, user):
        qs = self.alive()
        if not user.is_authenticated or not user.has_capability("agencies.view"):
            return qs.none()
        if user.role == "CONSULTANT":
            return qs.filter(pk=user.agency_id) if user.agency_id else qs.none()
        if user.role in ("SUPER_ADMIN", "ATLAS_RECRUITER"):
            return qs
        return qs.none()


class Agency(TimeStampedModel, SoftDeleteModel):
    """External recruiting partner (consultancy, staffing firm, job portal, referral channel...)."""

    class AgencyType(models.TextChoices):
        SEARCH = "search", "Specialist search agency"
        STAFFING = "staffing", "Staffing & sourcing agency"
        PORTAL = "portal", "Job portal"
        REFERRAL = "referral", "Referral network"
        CAMPUS = "campus", "Campus / institute"
        INDIVIDUAL = "individual", "Individual consultant"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        INACTIVE = "inactive", "Inactive"

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=24, unique=True)
    agency_type = models.CharField(max_length=16, choices=AgencyType.choices, default=AgencyType.STAFFING)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    contact_name = models.CharField(max_length=160, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=32, blank=True)
    commercial_terms = models.TextField(blank=True)
    sla_notes = models.TextField(blank=True)
    account_lead = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="managed_agencies",
    )

    objects = AgencyQuerySet.as_manager()

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "agencies"

    def __str__(self) -> str:
        return self.name

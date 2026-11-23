"""Development only: one demo user per role, a demo client and agency."""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.accounts.models import PermissionSet, Role, User
from apps.clients.models import Agency, Client


class Command(BaseCommand):
    help = "Create demo data for local development (refuses to run with DEBUG off)."

    def add_arguments(self, parser):
        parser.add_argument("--password", required=True, help="Password for every demo account")

    def handle(self, *args, **opts):
        if not settings.DEBUG:
            raise CommandError("seed_demo only runs with DEBUG=true.")
        internal, _ = Client.objects.get_or_create(
            code="ATLAS", defaults={"name": "NDT Atlas (internal hiring)", "is_internal": True}
        )
        client, _ = Client.objects.get_or_create(
            code="DEMO-CLIENT", defaults={"name": "Demo Client Inc.", "country": "United States"}
        )
        agency, _ = Agency.objects.get_or_create(
            code="DEMO-AGENCY", defaults={"name": "Demo Staffing Partners", "agency_type": "staffing"}
        )
        people = [
            ("admin@tis.local", Role.SUPER_ADMIN, {}),
            ("lead@tis.local", Role.ATLAS_RECRUITER, {"lead": True}),
            ("recruiter@tis.local", Role.ATLAS_RECRUITER, {}),
            ("client@tis.local", Role.CLIENT_USER, {"client": client}),
            ("consultant@tis.local", Role.CONSULTANT, {"agency": agency}),
            ("candidate@tis.local", Role.CANDIDATE, {}),
        ]
        lead_set = PermissionSet.objects.get(code="atlas_lead")
        for email, role, extra in people:
            lead = extra.pop("lead", False)
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "role": role,
                    "first_name": role.label.split()[0],
                    "last_name": "Demo",
                    "email_verified_at": timezone.now(),
                    "invite_accepted_at": timezone.now(),
                    **extra,
                },
            )
            if created:
                user.set_password(opts["password"])
                user.save()
            if lead:
                user.permission_sets.add(lead_set)
            self.stdout.write(f"{'created' if created else 'exists '} {email} ({role})")
        self.stdout.write(self.style.SUCCESS(f"Demo data ready. Internal client: {internal.name}"))

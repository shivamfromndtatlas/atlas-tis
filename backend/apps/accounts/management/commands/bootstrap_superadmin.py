"""Create the first Super Admin and email them an invite (no default passwords)."""

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import Role, User
from apps.accounts.services import send_invite


class Command(BaseCommand):
    help = "Create the first Super Admin and send a set-password invite."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--first-name", default="")
        parser.add_argument("--last-name", default="")

    def handle(self, *args, **opts):
        email = opts["email"].strip().lower()
        if User.objects.filter(email=email).exists():
            raise CommandError(f"{email} already exists.")
        user = User.objects.create_user(
            email=email, role=Role.SUPER_ADMIN, first_name=opts["first_name"], last_name=opts["last_name"]
        )
        send_invite(user)
        self.stdout.write(self.style.SUCCESS(f"Super Admin {email} created; invite email sent."))

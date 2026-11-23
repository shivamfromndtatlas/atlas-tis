"""Seed the role-default permission sets (the matrix) and the Atlas Lead add-on set."""

from django.db import migrations

ROLE_LABELS = {
    "ATLAS_RECRUITER": "Atlas Recruiter",
    "CLIENT_USER": "Client Recruiter / POC",
    "CONSULTANT": "Consultant",
    "CANDIDATE": "Candidate",
}


def seed(apps, schema_editor):
    from apps.accounts.capabilities import ADDON_SETS, ROLE_DEFAULTS

    PermissionSet = apps.get_model("accounts", "PermissionSet")
    for role, caps in ROLE_DEFAULTS.items():
        PermissionSet.objects.update_or_create(
            role_default=role,
            defaults={
                "code": f"role-{role.lower().replace('_', '-')}",
                "name": f"{ROLE_LABELS[role]} (default)",
                "capabilities": sorted(caps),
                "is_system": True,
            },
        )
    for code, spec in ADDON_SETS.items():
        PermissionSet.objects.update_or_create(
            code=code,
            defaults={
                "name": spec["name"],
                "description": spec["description"],
                "capabilities": sorted(spec["capabilities"]),
                "is_system": True,
            },
        )


def unseed(apps, schema_editor):
    PermissionSet = apps.get_model("accounts", "PermissionSet")
    PermissionSet.objects.filter(is_system=True).delete()


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_initial")]
    operations = [migrations.RunPython(seed, unseed)]

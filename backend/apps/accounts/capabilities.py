"""Capability registry: the single source of truth for the permission matrix.

Capabilities are checked on every request (never baked into tokens), so edits to the
matrix take effect immediately. SUPER_ADMIN implicitly holds every capability.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Capability:
    code: str
    group: str
    label: str
    description: str = ""


CAPABILITIES: tuple[Capability, ...] = (
    Capability("users.view", "Users", "View users"),
    Capability(
        "users.manage", "Users", "Create and edit any user", "Includes role changes and deactivation."
    ),
    Capability(
        "users.invite_external",
        "Users",
        "Invite client users and consultants",
        "Create and edit only CLIENT_USER and CONSULTANT accounts.",
    ),
    Capability("roles.manage", "Users", "Edit roles and permission sets"),
    Capability("clients.view", "Clients", "View clients", "Client users see only their own company."),
    Capability("clients.manage", "Clients", "Create, edit and archive clients and contacts"),
    Capability("agencies.view", "Agencies", "View consultant agencies"),
    Capability("agencies.manage", "Agencies", "Create, edit and archive consultant agencies"),
    Capability("audit.view", "Administration", "View the audit log"),
    Capability("settings.manage", "Administration", "Change system settings"),
    Capability("files.upload", "Files", "Upload documents"),
    Capability("files.view_all", "Files", "View documents across the organisation"),
)

CAPABILITY_CODES = frozenset(c.code for c in CAPABILITIES)

# Default capabilities per role, seeded into system permission sets and editable via the matrix.
ROLE_DEFAULTS: dict[str, list[str]] = {
    "ATLAS_RECRUITER": ["clients.view", "agencies.view", "files.upload", "files.view_all"],
    "CLIENT_USER": ["clients.view", "files.upload"],
    "CONSULTANT": ["agencies.view", "files.upload"],
    "CANDIDATE": ["files.upload"],
}

# Add-on permission sets seeded at install.
ADDON_SETS: dict[str, dict] = {
    "atlas_lead": {
        "name": "Atlas Lead",
        "description": "Recruitment managers and HR heads (spec section 3.1).",
        "capabilities": [
            "users.view",
            "users.invite_external",
            "clients.view",
            "clients.manage",
            "agencies.view",
            "agencies.manage",
            "audit.view",
            "files.upload",
            "files.view_all",
        ],
    }
}

# Roles and add-on sets that must enrol in MFA (spec section 15.1).
MFA_REQUIRED_ROLES = {"SUPER_ADMIN"}
MFA_REQUIRED_SETS = {"atlas_lead"}

from __future__ import annotations

from typing import Any

from apps.core.context import get_context

from .models import AuditLog

# Never written to the audit log, even as "changed".
SECRET_FIELDS = {"password", "mfa_secret", "code_hash"}
IGNORED_FIELDS = {"updated_at", "last_login", "token_version"}


def object_label(obj: Any) -> tuple[str, str, str]:
    if obj is None:
        return "", "", ""
    meta = obj._meta
    obj_type = f"{meta.app_label}.{meta.model_name}"
    obj_id = str(getattr(obj, "public_id", None) or obj.pk or "")
    return obj_type, obj_id, str(obj)[:255]


def record(action: str, obj: Any = None, changes: dict | None = None, actor: Any = None) -> AuditLog:
    ctx = get_context()
    actor = actor if actor is not None else ctx.actor
    if actor is not None and not getattr(actor, "is_authenticated", False):
        actor = None
    obj_type, obj_id, obj_repr = object_label(obj)
    return AuditLog.objects.create(
        actor=actor,
        actor_label=getattr(actor, "email", "") or "system",
        actor_role=getattr(actor, "role", "") or "",
        ip=ctx.ip,
        user_agent=ctx.user_agent,
        request_id=ctx.request_id,
        action=action,
        object_type=obj_type,
        object_id=obj_id,
        object_repr=obj_repr,
        changes=changes or {},
    )


def serialise_value(value: Any) -> Any:
    if value is None or isinstance(value, bool | int | float | str | list | dict):
        return value
    return str(value)

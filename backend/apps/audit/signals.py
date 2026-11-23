"""Automatic create/update/delete audit for registered models (field-level diffs)."""

from django.apps import apps
from django.db.models.signals import m2m_changed, post_delete, post_save, pre_save

from .services import IGNORED_FIELDS, SECRET_FIELDS, record, serialise_value

AUDITED_MODELS = [
    "accounts.User",
    "accounts.PermissionSet",
    "clients.Client",
    "clients.ClientContact",
    "clients.Agency",
    "files.Document",
    "files.DocumentVersion",
]


def _snapshot(instance) -> dict:
    data = {}
    for field in instance._meta.concrete_fields:
        if field.name in IGNORED_FIELDS:
            continue
        data[field.name] = serialise_value(getattr(instance, field.attname))
    return data


def _diff(before: dict, after: dict) -> dict:
    changes = {}
    for key in set(before) | set(after):
        if before.get(key) != after.get(key):
            if key in SECRET_FIELDS:
                changes[key] = {"changed": True}
            else:
                changes[key] = {"from": before.get(key), "to": after.get(key)}
    return changes


def _pre_save(sender, instance, **kwargs):
    if instance.pk:
        old = sender._default_manager.filter(pk=instance.pk).first()
        instance._audit_before = _snapshot(old) if old else None
    else:
        instance._audit_before = None


def _post_save(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    after = _snapshot(instance)
    if created:
        changes = {
            k: {"to": v} for k, v in after.items() if k not in SECRET_FIELDS and v not in (None, "", [], {})
        }
        record("create", instance, changes)
        return
    before = getattr(instance, "_audit_before", None) or {}
    changes = _diff(before, after)
    if changes:
        action = "soft_delete" if "deleted_at" in changes and after.get("deleted_at") else "update"
        record(action, instance, changes)


def _post_delete(sender, instance, **kwargs):
    record("delete", instance, {})


def _m2m_changed(sender, instance, action, pk_set, **kwargs):
    if action in ("post_add", "post_remove", "post_clear"):
        record(
            "update",
            instance,
            {sender._meta.model_name: {action.replace("post_", ""): sorted(pk_set or [])}},
        )


for label in AUDITED_MODELS:
    model = apps.get_model(label)
    uid = f"audit-{label}"
    pre_save.connect(_pre_save, sender=model, dispatch_uid=f"{uid}-pre")
    post_save.connect(_post_save, sender=model, dispatch_uid=f"{uid}-post")
    post_delete.connect(_post_delete, sender=model, dispatch_uid=f"{uid}-del")

m2m_changed.connect(
    _m2m_changed,
    sender=apps.get_model("accounts.User").permission_sets.through,
    dispatch_uid="audit-user-sets",
)

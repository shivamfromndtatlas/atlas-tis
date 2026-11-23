"""Capability-based permissions (layer 1 of spec section 3.3).

Views declare ``capability_map = {"list": "clients.view", "create": "clients.manage", ...}``.
``"*"`` is the fallback key. ``None`` means "authenticated is enough" (row scoping still applies).
Row scoping (layer 2) lives in each model manager's ``for_user()``.
"""

from rest_framework.permissions import BasePermission

_MISSING = object()


class HasCapability(BasePermission):
    message = "You do not have permission to perform this action."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        mapping = getattr(view, "capability_map", {}) or {}
        if hasattr(view, "action") and view.action is None:
            return True  # viewset has no handler for this method -> let DRF answer 405
        action = getattr(view, "action", None) or request.method.lower()
        required = mapping.get(action, mapping.get("*", _MISSING))
        if required is _MISSING:
            return False  # deny by default when a view forgets to declare an action
        if required is None:
            return True
        if isinstance(required, str):
            required = (required,)
        return any(user.has_capability(code) for code in required)

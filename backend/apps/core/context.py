"""Per-request context (actor, IP, request id) used by audit logging.

Uses contextvars so it is safe under threads and async workers.
"""

from __future__ import annotations

import contextvars
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RequestContext:
    request_id: str = ""
    ip: str | None = None
    user_agent: str = ""
    actor: Any = None
    extra: dict = field(default_factory=dict)


_ctx: contextvars.ContextVar[RequestContext | None] = contextvars.ContextVar("tis_request_ctx", default=None)


def get_context() -> RequestContext:
    ctx = _ctx.get()
    if ctx is None:
        ctx = RequestContext()
        _ctx.set(ctx)
    return ctx


def set_context(ctx: RequestContext) -> contextvars.Token:
    return _ctx.set(ctx)


def reset_context(token: contextvars.Token) -> None:
    _ctx.reset(token)


def set_actor(user: Any) -> None:
    get_context().actor = user

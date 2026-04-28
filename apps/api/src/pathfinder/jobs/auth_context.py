"""Re-install request-scoped ContextVars at the worker boundary.

Procrastinate workers don't inherit the dispatching api process's
``ContextVar`` state. Job payloads carry the values across; these helpers
re-install them for the job body and reset them on exit.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from pathfinder.platform.context import user_id_ctx, veupathdb_auth_token_ctx


@asynccontextmanager
async def attach_wdk_auth(token: str | None) -> AsyncIterator[None]:
    """Set ``veupathdb_auth_token_ctx`` to ``token`` inside the block."""
    reset = veupathdb_auth_token_ctx.set(token)
    try:
        yield
    finally:
        veupathdb_auth_token_ctx.reset(reset)


@asynccontextmanager
async def attach_user_id(user_id: UUID | None) -> AsyncIterator[None]:
    """Set ``user_id_ctx`` to ``user_id`` inside the block."""
    reset = user_id_ctx.set(user_id)
    try:
        yield
    finally:
        user_id_ctx.reset(reset)


__all__ = ["attach_user_id", "attach_wdk_auth"]

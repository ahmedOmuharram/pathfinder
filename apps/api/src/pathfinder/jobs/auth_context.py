"""Lifecycle helper for ``veupathdb_auth_token_ctx`` at the worker boundary.

Procrastinate runs tasks in a worker process that has no inherited
``ContextVar`` state from the dispatching api process. The typed job payload
(see ``pathfinder.jobs.payloads``) carries the cookie string across the
process boundary; this context manager is the paired helper that re-installs
it on the ctxvar for the duration of the job body, then restores the prior
value on exit (so subsequent worker tasks do not inherit the cookie).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from pathfinder.platform.context import veupathdb_auth_token_ctx


@asynccontextmanager
async def attach_wdk_auth(token: str | None) -> AsyncIterator[None]:
    """Set ``veupathdb_auth_token_ctx`` to ``token`` inside the block."""
    reset = veupathdb_auth_token_ctx.set(token)
    try:
        yield
    finally:
        veupathdb_auth_token_ctx.reset(reset)


__all__ = ["attach_wdk_auth"]

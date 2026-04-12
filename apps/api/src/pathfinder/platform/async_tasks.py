"""Async task helpers."""

import asyncio
import contextvars
from collections.abc import Coroutine
from typing import Any


def create_detached_task[T](
    coro: Coroutine[Any, Any, T],
    *,
    name: str | None = None,
) -> asyncio.Task[T]:
    """Start a task in a fresh context.

    This prevents request-scoped contextvars, including active OTEL spans,
    from leaking into background producers that should own their own trace.
    """
    detached_context = contextvars.Context()
    return asyncio.create_task(coro, name=name, context=detached_context)

"""Tests for detached task helpers."""

import contextvars

from pathfinder.platform.async_tasks import create_detached_task


async def test_create_detached_task_drops_parent_contextvars() -> None:
    """Detached tasks should not inherit the parent contextvars."""
    marker = contextvars.ContextVar("marker", default="unset")
    marker.set("parent")

    async def read_marker() -> str:
        return marker.get()

    task = create_detached_task(read_marker(), name="detached-marker")
    assert await task == "unset"

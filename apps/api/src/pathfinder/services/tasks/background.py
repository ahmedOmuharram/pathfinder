"""Background-task service: create durable-task rows.

Wraps ``BackgroundTaskRepository`` so callers (e.g. the ``@durable_tool``
decorator in the AI layer) never import persistence directly.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.persistence.models import BackgroundTask
from pathfinder.persistence.repositories.background_tasks import (
    BackgroundTaskRepository,
)
from pathfinder.platform.db import async_session_factory

_ACTIVE_TASK_STATUSES: frozenset[str] = frozenset({"pending", "running", "resuming"})


async def has_active_task(
    session: AsyncSession,
    conversation_id: UUID,
    user_id: UUID,
) -> bool:
    """Whether the conversation has a pending/running/resuming durable task."""
    found = await session.scalar(
        select(BackgroundTask.id)
        .where(
            BackgroundTask.conversation_id == conversation_id,
            BackgroundTask.user_id == user_id,
            BackgroundTask.status.in_(_ACTIVE_TASK_STATUSES),
        )
        .limit(1),
    )
    return found is not None


async def create_background_task(
    *,
    conversation_id: UUID,
    user_id: UUID,
    tool_name: str,
    args: dict[str, Any],
    estimated_duration_seconds: int,
) -> UUID:
    """Create a ``background_tasks`` row and return its id."""
    repo = BackgroundTaskRepository(session_factory=async_session_factory)
    return await repo.create(
        conversation_id=conversation_id,
        user_id=user_id,
        tool_name=tool_name,
        args=args,
        estimated_duration_seconds=estimated_duration_seconds,
    )

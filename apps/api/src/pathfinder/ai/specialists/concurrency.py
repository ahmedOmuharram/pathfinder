"""Concurrency guards shared by specialist enter and launcher endpoints.

A conversation may have at most one active specialist mode AND zero
in-flight durable background tasks at the moment we mutate state. This
helper centralizes the check so the policy is consistent.
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pathfinder.persistence.models import Conversation
from pathfinder.persistence.repositories.background_tasks import (
    BackgroundTaskRepository,
)
from pathfinder.persistence.session import async_session_factory


class ActiveSessionReason(StrEnum):
    SPECIALIST_ACTIVE = "specialist_active"
    DURABLE_TASK_ACTIVE = "durable_task_active"


class ActiveSessionConflictError(Exception):
    """Raised when a conversation already has an active session."""

    def __init__(self, *, reason: ActiveSessionReason, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


async def _list_inflight_task_names(conversation_id: UUID) -> list[str]:
    bg_repo = BackgroundTaskRepository(session_factory=async_session_factory)
    active = await bg_repo.list_active_for_conversation(
        conversation_id=conversation_id,
    )
    return sorted({t.tool_name for t in active})


async def assert_no_active_session(
    *, conversation: Conversation,
) -> None:
    """Raise ``ActiveSessionConflict`` if a specialist or durable task is in flight."""
    if conversation.specialist_mode is not None:
        raise ActiveSessionConflictError(
            reason=ActiveSessionReason.SPECIALIST_ACTIVE,
            detail=(
                "A specialist mode is already active on this conversation. "
                "Type /done to exit before starting another."
            ),
        )
    names = await _list_inflight_task_names(conversation.id)
    if names:
        raise ActiveSessionConflictError(
            reason=ActiveSessionReason.DURABLE_TASK_ACTIVE,
            detail=(
                f"Background task(s) running ({', '.join(names)}) — wait "
                "for completion or cancel before starting a specialist."
            ),
        )


async def assert_no_inflight_durable_task(
    *, conversation_id: UUID,
) -> None:
    """Raise when an in-flight durable task exists. Used by the specialist
    exit endpoint to refuse ``/done`` while a specialist-spawned task is
    still running."""
    names = await _list_inflight_task_names(conversation_id)
    if names:
        raise ActiveSessionConflictError(
            reason=ActiveSessionReason.DURABLE_TASK_ACTIVE,
            detail=(
                f"Cannot exit while background task(s) are running "
                f"({', '.join(names)}). Wait for completion or cancel them."
            ),
        )

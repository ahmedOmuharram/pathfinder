"""Per-user preferences persisted server-side on the ``users`` row.

Currently one field:

* ``supervisor_model_id`` — catalog id (e.g. ``anthropic/claude-sonnet-4-5``)
  overriding the orchestrator's default model. ``None`` = auto (use the
  smallest model of the configured default provider).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.models.catalog import get_model_entry
from pathfinder.persistence.models import Conversation, User


@dataclass(frozen=True)
class UserPreferences:
    supervisor_model_id: str | None


class UnknownModelError(ValueError):
    """Raised when a supervisor_model_id doesn't match the catalog."""


async def get_preferences(session: AsyncSession, user_id: UUID) -> UserPreferences:
    row = await session.scalar(
        select(User.supervisor_model_id).where(User.id == user_id),
    )
    return UserPreferences(supervisor_model_id=row)


async def resolve_supervisor_model_id(
    session: AsyncSession, *, user_id: UUID, conversation_id: UUID,
) -> str | None:
    """Conversation override → user default → None (auto)."""
    result = await session.execute(
        select(
            Conversation.supervisor_model_id,
            User.supervisor_model_id,
        )
        .join(User, User.id == Conversation.user_id)
        .where(Conversation.id == conversation_id, User.id == user_id),
    )
    row = result.one_or_none()
    if row is None:
        return None
    conv_pref: str | None = row[0]
    user_pref: str | None = row[1]
    return conv_pref if conv_pref is not None else user_pref


async def apply_patch(
    session: AsyncSession, user_id: UUID, patch: dict[str, Any],
) -> UserPreferences:
    """Apply a partial update. Only keys present in ``patch`` are written."""
    values: dict[str, str | None] = {}
    if "supervisor_model_id" in patch:
        value = patch["supervisor_model_id"]
        if value is not None:
            if not isinstance(value, str):
                msg = "supervisor_model_id must be a string or null"
                raise UnknownModelError(msg)
            if get_model_entry(value) is None:
                msg = f"unknown supervisor_model_id: {value}"
                raise UnknownModelError(msg)
        values["supervisor_model_id"] = value
    if values:
        await session.execute(
            update(User).where(User.id == user_id).values(**values),
        )
        await session.commit()
    return await get_preferences(session, user_id)

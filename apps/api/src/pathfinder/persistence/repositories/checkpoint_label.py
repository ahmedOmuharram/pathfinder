from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.persistence.models import CheckpointLabel

SessionFactory = Callable[[], AsyncSession]


class CheckpointLabelRow(BaseModel):
    """Pydantic projection of a ``CheckpointLabel`` row.

    Constructed via ``model_validate`` against the SQLAlchemy ORM instance —
    callers receive a typed value and never touch the ORM mapping directly.
    """

    model_config = ConfigDict(from_attributes=True)

    thread_id: str
    checkpoint_id: str
    user_id: UUID
    label: str | None
    pinned: bool
    created_at: datetime
    updated_at: datetime


class CheckpointLabelRepository:
    """CRUD for per-user labels + pin flags attached to LangGraph checkpoints."""

    def __init__(self, *, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def set_label(
        self,
        *,
        thread_id: str,
        checkpoint_id: str,
        user_id: UUID,
        label: str | None,
        pinned: bool,
    ) -> CheckpointLabelRow:
        """Insert or update the label for ``(thread_id, checkpoint_id, user_id)``.

        Idempotent: a second call replaces the existing row's label and pin
        flag and bumps ``updated_at``.
        """
        now = datetime.now(UTC)
        async with self._session_factory() as session:
            stmt = (
                pg_insert(CheckpointLabel)
                .values(
                    thread_id=thread_id,
                    checkpoint_id=checkpoint_id,
                    user_id=user_id,
                    label=label,
                    pinned=pinned,
                    updated_at=now,
                )
                .on_conflict_do_update(
                    index_elements=["thread_id", "checkpoint_id", "user_id"],
                    set_={
                        "label": label,
                        "pinned": pinned,
                        "updated_at": now,
                    },
                )
                .returning(CheckpointLabel)
            )
            result = await session.execute(stmt)
            row = result.scalar_one()
            await session.commit()
            await session.refresh(row)
            return CheckpointLabelRow.model_validate(row)

    async def delete_label(
        self,
        *,
        thread_id: str,
        checkpoint_id: str,
        user_id: UUID,
    ) -> None:
        """Drop the label row for the ``(thread, checkpoint, user)`` triple."""
        async with self._session_factory() as session:
            await session.execute(
                delete(CheckpointLabel).where(
                    CheckpointLabel.thread_id == thread_id,
                    CheckpointLabel.checkpoint_id == checkpoint_id,
                    CheckpointLabel.user_id == user_id,
                )
            )
            await session.commit()

    async def list_for_thread(
        self,
        *,
        thread_id: str,
        user_id: UUID,
    ) -> list[CheckpointLabelRow]:
        """Return every label this user has on this thread, oldest first."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(CheckpointLabel)
                .where(
                    CheckpointLabel.thread_id == thread_id,
                    CheckpointLabel.user_id == user_id,
                )
                .order_by(CheckpointLabel.created_at.asc())
            )
            return [
                CheckpointLabelRow.model_validate(r) for r in result.scalars()
            ]

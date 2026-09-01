"""The EDA analysis a thread has open. One row per thread, or none."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.persistence.models import (
    ConversationAnalysis,
    ConversationAnalysisView,
)

SessionFactory = Callable[[], AsyncSession]

__all__ = [
    "ConversationAnalysesRepository",
    "bind_analysis_row",
    "bump_analysis_row",
    "read_analysis_row",
    "unbind_analysis_row",
]


async def read_analysis_row(
    session: AsyncSession,
    *,
    conversation_id: UUID,
) -> ConversationAnalysisView | None:
    row = (
        await session.execute(
            select(ConversationAnalysis).where(
                ConversationAnalysis.conversation_id == conversation_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    return ConversationAnalysisView.model_validate(row)


async def bind_analysis_row(
    session: AsyncSession,
    *,
    conversation_id: UUID,
    site_id: str,
    dataset_id: str,
    analysis_id: str,
) -> None:
    """Bind this analysis, replacing whatever the thread had open.

    A replacement is a different document, so the revision restarts.
    """
    values = {
        "site_id": site_id,
        "dataset_id": dataset_id,
        "analysis_id": analysis_id,
        "revision": 0,
    }
    await session.execute(
        insert(ConversationAnalysis)
        .values(conversation_id=conversation_id, **values)
        .on_conflict_do_update(
            index_elements=[ConversationAnalysis.conversation_id],
            set_=values,
        ),
    )


async def bump_analysis_row(
    session: AsyncSession,
    *,
    conversation_id: UUID,
) -> int:
    """The new revision, or 0 when the thread has no analysis open."""
    revision = (
        await session.execute(
            update(ConversationAnalysis)
            .where(ConversationAnalysis.conversation_id == conversation_id)
            .values(revision=ConversationAnalysis.revision + 1)
            .returning(ConversationAnalysis.revision)
        )
    ).scalar_one_or_none()
    return revision or 0


async def unbind_analysis_row(
    session: AsyncSession,
    *,
    conversation_id: UUID,
) -> None:
    await session.execute(
        delete(ConversationAnalysis).where(
            ConversationAnalysis.conversation_id == conversation_id
        )
    )


class ConversationAnalysesRepository:
    """Bind, read, count and clear a thread's open analysis.

    Every method owns its transaction, because an agent tool calling one holds
    no session of its own. Thread surgery runs inside the caller's transaction
    and calls the row functions above instead.
    """

    def __init__(self, *, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def get(
        self,
        *,
        conversation_id: UUID,
    ) -> ConversationAnalysisView | None:
        async with self._session_factory() as session:
            return await read_analysis_row(session, conversation_id=conversation_id)

    async def bind(
        self,
        *,
        conversation_id: UUID,
        site_id: str,
        dataset_id: str,
        analysis_id: str,
    ) -> None:
        async with self._session_factory() as session:
            await bind_analysis_row(
                session,
                conversation_id=conversation_id,
                site_id=site_id,
                dataset_id=dataset_id,
                analysis_id=analysis_id,
            )
            await session.commit()

    async def increment(self, *, conversation_id: UUID) -> int:
        """The new revision, or 0 when the thread has no analysis open.

        A bound row reaches 1 on its first mutation, so 0 never names one.
        """
        async with self._session_factory() as session:
            revision = await bump_analysis_row(
                session,
                conversation_id=conversation_id,
            )
            await session.commit()
            return revision

    async def unbind(self, *, conversation_id: UUID) -> None:
        async with self._session_factory() as session:
            await unbind_analysis_row(session, conversation_id=conversation_id)
            await session.commit()

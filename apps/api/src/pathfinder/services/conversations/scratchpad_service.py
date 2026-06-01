"""Scratchpad read/write service (notes + compaction audit log)."""

from typing import Literal, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.domain.scratchpad.models import CompactionRun, Note
from pathfinder.persistence.models import ScratchpadCompaction
from pathfinder.persistence.repositories import ConversationRepository
from pathfinder.persistence.repositories.scratchpad import ScratchpadRepository
from pathfinder.platform.errors import NotFoundError
from pathfinder.services.conversations.authz import get_owned_or_404


class ScratchpadService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _verify(self, conversation_id: UUID, user_id: UUID) -> None:
        await get_owned_or_404(
            ConversationRepository(self._session),
            conversation_id,
            user_id,
        )

    async def list_notes(self, conversation_id: UUID, user_id: UUID) -> list[Note]:
        await self._verify(conversation_id, user_id)
        repo = ScratchpadRepository(self._session)
        return await repo.list_notes(conversation_id=conversation_id, limit=200)

    async def get_note(
        self,
        conversation_id: UUID,
        note_id: str,
        user_id: UUID,
    ) -> Note:
        await self._verify(conversation_id, user_id)
        note = await ScratchpadRepository(self._session).get(
            conversation_id=conversation_id,
            note_id=note_id,
        )
        if note is None:
            raise NotFoundError(title="note not found")
        return note

    async def set_pinned(
        self,
        conversation_id: UUID,
        note_id: str,
        *,
        pinned: bool,
        user_id: UUID,
    ) -> Note:
        await self._verify(conversation_id, user_id)
        try:
            updated = await ScratchpadRepository(self._session).set_pinned(
                conversation_id=conversation_id,
                note_id=note_id,
                pinned=pinned,
            )
        except LookupError as exc:
            raise NotFoundError(title="note not found") from exc
        await self._session.commit()
        return updated

    async def delete_note(
        self,
        conversation_id: UUID,
        note_id: str,
        user_id: UUID,
    ) -> None:
        await self._verify(conversation_id, user_id)
        ok = await ScratchpadRepository(self._session).delete(
            conversation_id=conversation_id,
            note_id=note_id,
        )
        if not ok:
            raise NotFoundError(title="note not found")
        await self._session.commit()

    async def list_compactions(
        self,
        conversation_id: UUID,
        user_id: UUID,
    ) -> list[CompactionRun]:
        await self._verify(conversation_id, user_id)
        stmt = (
            select(ScratchpadCompaction)
            .where(ScratchpadCompaction.conversation_id == conversation_id)
            .order_by(ScratchpadCompaction.triggered_at.desc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            CompactionRun(
                id=r.id,
                conversation_id=r.conversation_id,
                triggered_at=r.triggered_at,
                before_count=r.before_count,
                after_count=r.after_count,
                before_tokens=r.before_tokens,
                after_tokens=r.after_tokens,
                model_id=r.model_id,
                cost_usd=r.cost_usd,
                trigger_reason=cast(
                    "Literal['count', 'tokens', 'both']",
                    r.trigger_reason,
                ),
            )
            for r in rows
        ]

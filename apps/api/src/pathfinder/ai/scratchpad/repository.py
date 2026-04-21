from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import CursorResult, and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.scratchpad._ids import approx_body_tokens, mint_note_id
from pathfinder.ai.scratchpad.models import (
    CompactionRun,
    Note,
    NoteCreate,
    NoteUpdate,
)
from pathfinder.persistence.models import ScratchpadCompaction, ScratchpadNote
from pathfinder.platform.logging import get_logger

logger = get_logger(__name__)


def _row_to_note(row: ScratchpadNote) -> Note:
    return Note.model_validate(row, from_attributes=True)


class ScratchpadRepository:
    """Scratchpad persistence — all public methods return Pydantic models."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self, *, conversation_id: UUID, data: NoteCreate,
    ) -> Note:
        note_id = mint_note_id()
        row = ScratchpadNote(
            id=note_id,
            conversation_id=conversation_id,
            title=data.title,
            summary=data.summary,
            body=data.body,
            tags=list(data.tags),
            pinned=data.pinned,
            body_tokens=approx_body_tokens(data.body),
        )
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return _row_to_note(row)

    async def get(
        self, *, conversation_id: UUID, note_id: str,
    ) -> Note | None:
        stmt = select(ScratchpadNote).where(
            and_(
                ScratchpadNote.id == note_id,
                ScratchpadNote.conversation_id == conversation_id,
            ),
        )
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        return _row_to_note(row) if row is not None else None

    async def update(
        self, *, conversation_id: UUID, note_id: str, patch: NoteUpdate,
    ) -> Note:
        stmt = select(ScratchpadNote).where(
            and_(
                ScratchpadNote.id == note_id,
                ScratchpadNote.conversation_id == conversation_id,
            ),
        )
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is None:
            msg = f"note not found: {note_id}"
            raise LookupError(msg)
        if patch.title is not None:
            row.title = patch.title
        if patch.summary is not None:
            row.summary = patch.summary
        if patch.body is not None:
            row.body = patch.body
            row.body_tokens = approx_body_tokens(patch.body)
        if patch.tags is not None:
            row.tags = list(patch.tags)
        row.updated_at = datetime.now(UTC)
        await self.session.flush()
        return _row_to_note(row)

    async def delete(
        self, *, conversation_id: UUID, note_id: str,
    ) -> bool:
        stmt = delete(ScratchpadNote).where(
            and_(
                ScratchpadNote.id == note_id,
                ScratchpadNote.conversation_id == conversation_id,
            ),
        )
        result = cast("CursorResult[object]", await self.session.execute(stmt))
        return (result.rowcount or 0) > 0

    async def set_pinned(
        self, *, conversation_id: UUID, note_id: str, pinned: bool,
    ) -> Note:
        stmt = select(ScratchpadNote).where(
            and_(
                ScratchpadNote.id == note_id,
                ScratchpadNote.conversation_id == conversation_id,
            ),
        )
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is None:
            msg = f"note not found: {note_id}"
            raise LookupError(msg)
        row.pinned = pinned
        row.updated_at = datetime.now(UTC)
        await self.session.flush()
        return _row_to_note(row)

    async def list_notes(
        self,
        *,
        conversation_id: UUID,
        tag: str | None = None,
        pinned: bool | None = None,
        limit: int = 100,
    ) -> list[Note]:
        stmt = select(ScratchpadNote).where(
            ScratchpadNote.conversation_id == conversation_id,
        )
        if pinned is not None:
            stmt = stmt.where(ScratchpadNote.pinned == pinned)
        if tag is not None:
            stmt = stmt.where(
                ScratchpadNote.tags.op("@>")([tag.lower().strip()]),
            )
        stmt = stmt.order_by(
            ScratchpadNote.pinned.desc(),
            ScratchpadNote.created_at.desc(),
        ).limit(limit)
        rows = (await self.session.execute(stmt)).scalars().all()
        return [_row_to_note(r) for r in rows]

    async def search_notes(
        self, *, conversation_id: UUID, query: str, limit: int = 10,
    ) -> list[Note]:
        q = query.strip()
        if not q:
            return []
        tsq = func.websearch_to_tsquery("english", q)
        stmt = (
            select(ScratchpadNote)
            .where(
                and_(
                    ScratchpadNote.conversation_id == conversation_id,
                    ScratchpadNote.fts.op("@@")(tsq),
                ),
            )
            .order_by(func.ts_rank(ScratchpadNote.fts, tsq).desc())
            .limit(limit)
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return [_row_to_note(r) for r in rows]

    async def list_for_index_with_totals(
        self, *, conversation_id: UUID, recent_limit: int = 10,
    ) -> tuple[list[Note], int, int]:
        """Combined index fetch: ``(notes_for_index, total_count, total_tokens)``.

        Collapses the two-roundtrip ``list_for_index`` + ``totals`` pattern
        used by the supervisor state block and the ``pinned_scratchpad``
        dynamic instruction into a single session visit.
        """
        notes = await self.list_for_index(
            conversation_id=conversation_id, recent_limit=recent_limit,
        )
        total_count, total_tokens = await self.totals(
            conversation_id=conversation_id,
        )
        return notes, total_count, total_tokens

    async def list_for_index(
        self, *, conversation_id: UUID, recent_limit: int = 10,
    ) -> list[Note]:
        """Pinned notes (oldest→newest) plus last-N non-pinned (newest→oldest).

        Pinned-first keeps load-bearing context at the top of the rendered
        index.
        """
        pinned_stmt = (
            select(ScratchpadNote)
            .where(
                and_(
                    ScratchpadNote.conversation_id == conversation_id,
                    ScratchpadNote.pinned.is_(True),
                ),
            )
            .order_by(ScratchpadNote.created_at.asc())
        )
        recent_stmt = (
            select(ScratchpadNote)
            .where(
                and_(
                    ScratchpadNote.conversation_id == conversation_id,
                    ScratchpadNote.pinned.is_(False),
                ),
            )
            .order_by(ScratchpadNote.created_at.desc())
            .limit(recent_limit)
        )
        pinned = (await self.session.execute(pinned_stmt)).scalars().all()
        recent = (await self.session.execute(recent_stmt)).scalars().all()
        return [
            *(_row_to_note(r) for r in pinned),
            *(_row_to_note(r) for r in recent),
        ]

    async def totals(self, *, conversation_id: UUID) -> tuple[int, int]:
        """All notes (pinned + non-pinned). Use for UI-facing "how big" labels.

        The compactor must NOT use this — pinned notes are untouchable during
        compaction, so including them in the gating count causes infinite
        re-triggering when the non-pinned tail is below threshold but the
        pinned set pushes the total over it. Use ``compactable_totals``
        instead for that gate.
        """
        stmt = select(
            func.count(ScratchpadNote.id),
            func.coalesce(func.sum(ScratchpadNote.body_tokens), 0),
        ).where(ScratchpadNote.conversation_id == conversation_id)
        row = (await self.session.execute(stmt)).one()
        count = int(row[0])
        tokens = int(row[1])
        return count, tokens

    async def compactable_totals(
        self, *, conversation_id: UUID,
    ) -> tuple[int, int]:
        """Non-pinned notes only — the subset the compactor can act on."""
        stmt = select(
            func.count(ScratchpadNote.id),
            func.coalesce(func.sum(ScratchpadNote.body_tokens), 0),
        ).where(
            and_(
                ScratchpadNote.conversation_id == conversation_id,
                ScratchpadNote.pinned.is_(False),
            ),
        )
        row = (await self.session.execute(stmt)).one()
        count = int(row[0])
        tokens = int(row[1])
        return count, tokens

    async def replace_non_pinned(
        self, *, conversation_id: UUID, new_notes: list[NoteCreate],
    ) -> list[Note]:
        """Atomic: delete non-pinned rows, insert the replacements."""
        async with self.session.begin_nested():
            del_stmt = delete(ScratchpadNote).where(
                and_(
                    ScratchpadNote.conversation_id == conversation_id,
                    ScratchpadNote.pinned.is_(False),
                ),
            )
            await self.session.execute(del_stmt)

            inserted: list[Note] = []
            for data in new_notes:
                created = await self.create(
                    conversation_id=conversation_id, data=data,
                )
                inserted.append(created)
        return inserted

    async def copy_notes_for_fork(
        self,
        *,
        source_conversation_id: UUID,
        target_conversation_id: UUID,
    ) -> dict[str, str]:
        """Duplicate every note from ``source`` under ``target`` with fresh ids.

        Returns a mapping ``{old_id: new_id}`` so callers can rewrite stored
        tool-call blobs / message parts that reference the old ids. The fork
        must NOT share ids with the source — they live under different
        conversation scopes, and a future update/delete in the fork would
        silently clobber the source otherwise.
        """
        stmt = select(ScratchpadNote).where(
            ScratchpadNote.conversation_id == source_conversation_id,
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        id_map: dict[str, str] = {}
        for src in rows:
            new_id = mint_note_id()
            id_map[src.id] = new_id
            self.session.add(
                ScratchpadNote(
                    id=new_id,
                    conversation_id=target_conversation_id,
                    title=src.title,
                    summary=src.summary,
                    body=src.body,
                    tags=list(src.tags),
                    pinned=src.pinned,
                    body_tokens=src.body_tokens,
                ),
            )
        await self.session.flush()
        return id_map

    async def log_compaction(self, *, run: CompactionRun) -> None:
        row = ScratchpadCompaction(
            conversation_id=run.conversation_id,
            triggered_at=run.triggered_at,
            before_count=run.before_count,
            after_count=run.after_count,
            before_tokens=run.before_tokens,
            after_tokens=run.after_tokens,
            model_id=run.model_id,
            cost_usd=run.cost_usd,
            trigger_reason=run.trigger_reason,
        )
        self.session.add(row)
        await self.session.flush()

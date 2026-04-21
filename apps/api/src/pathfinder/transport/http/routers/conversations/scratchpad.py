"""Scratchpad HTTP routes — list/get/patch(pin)/delete + compaction audit log."""
from __future__ import annotations

from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ConfigDict, Field
from sqlalchemy import select

from pathfinder.ai.scratchpad.models import CompactionRun, Note
from pathfinder.ai.scratchpad.repository import ScratchpadRepository
from pathfinder.persistence.models import ScratchpadCompaction
from pathfinder.persistence.repositories import ConversationRepository
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.transport.http.deps import CurrentUser, DBSession

router = APIRouter(prefix="/api/v1/conversations", tags=["scratchpad"])


class ScratchpadPatchRequest(CamelModel):
    """User-driven PATCH — only the ``pinned`` flag is settable from the UI.

    ``extra="forbid"`` rejects ``title``/``body``/``summary`` edits with 422
    so scratchpad content stays agent-authored.
    """

    model_config = ConfigDict(extra="forbid")

    pinned: bool = Field(description="New pin state.")


async def verified_conversation(
    conversation_id: UUID,
    session: DBSession,
    user_id: CurrentUser,
) -> UUID:
    """Ensure ``user_id`` owns ``conversation_id`` before the route runs."""
    repo = ConversationRepository(session)
    conv = await repo.get_by_id(conversation_id)
    if conv is None or conv.user_id != user_id:
        raise HTTPException(status_code=404, detail="conversation not found")
    return conversation_id


VerifiedConversation = Annotated[UUID, Depends(verified_conversation)]


@router.get(
    "/{conversation_id}/scratchpad/notes",
    response_model=list[Note],
    summary="List scratchpad notes for the conversation.",
)
async def list_scratchpad_notes(
    conversation_id: VerifiedConversation, session: DBSession,
) -> list[Note]:
    repo = ScratchpadRepository(session)
    return await repo.list_notes(conversation_id=conversation_id, limit=200)


@router.get(
    "/{conversation_id}/scratchpad/notes/{note_id}",
    response_model=Note,
    summary="Get a single scratchpad note.",
)
async def get_scratchpad_note(
    conversation_id: VerifiedConversation,
    note_id: str,
    session: DBSession,
) -> Note:
    repo = ScratchpadRepository(session)
    note = await repo.get(conversation_id=conversation_id, note_id=note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="note not found")
    return note


@router.patch(
    "/{conversation_id}/scratchpad/notes/{note_id}",
    response_model=Note,
    summary="Pin or unpin a scratchpad note.",
)
async def patch_scratchpad_note(
    conversation_id: VerifiedConversation,
    note_id: str,
    request: ScratchpadPatchRequest,
    session: DBSession,
) -> Note:
    repo = ScratchpadRepository(session)
    try:
        updated = await repo.set_pinned(
            conversation_id=conversation_id,
            note_id=note_id,
            pinned=request.pinned,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="note not found") from exc
    await session.commit()
    return updated


@router.delete(
    "/{conversation_id}/scratchpad/notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a scratchpad note.",
)
async def delete_scratchpad_note(
    conversation_id: VerifiedConversation,
    note_id: str,
    session: DBSession,
) -> None:
    repo = ScratchpadRepository(session)
    ok = await repo.delete(conversation_id=conversation_id, note_id=note_id)
    if not ok:
        raise HTTPException(status_code=404, detail="note not found")
    await session.commit()


@router.get(
    "/{conversation_id}/scratchpad/compactions",
    response_model=list[CompactionRun],
    summary="Audit log for scratchpad compaction runs.",
)
async def list_compactions(
    conversation_id: VerifiedConversation, session: DBSession,
) -> list[CompactionRun]:
    stmt = (
        select(ScratchpadCompaction)
        .where(ScratchpadCompaction.conversation_id == conversation_id)
        .order_by(ScratchpadCompaction.triggered_at.desc())
    )
    rows = (await session.execute(stmt)).scalars().all()
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
                "Literal['count', 'tokens', 'both']", r.trigger_reason,
            ),
        )
        for r in rows
    ]

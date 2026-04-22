from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from pydantic import ValidationError
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.messages import ModelResponse, ToolCallPart, ToolReturn
from pydantic_ai.tools import RunContext, ToolDefinition
from pydantic_ai.toolsets.abstract import AbstractToolset
from pydantic_ai.toolsets.function import FunctionToolset
from pydantic_ai.toolsets.prepared import PreparedToolset

from pathfinder.ai.graph.runtime import AgentDeps, DBSessionFactory
from pathfinder.ai.graph.stream_events import scratchpad_updated_event
from pathfinder.ai.memory.schemas import MemoryValue
from pathfinder.ai.memory.store import MemoryStore
from pathfinder.ai.scratchpad.models import (
    Note,
    NoteCreate,
    NoteDetail,
    NoteRef,
    NoteUpdate,
)
from pathfinder.ai.scratchpad.repository import ScratchpadRepository
from pathfinder.platform.logging import get_logger

logger = get_logger(__name__)

_MSG_MISSING_CTX = "scratchpad unavailable: missing conversation context"
_MSG_MEMORY_UNAVAILABLE = "memory store unavailable"


def _ref_payload(note: Note) -> dict[str, object]:
    return NoteRef.model_validate(note, from_attributes=True).model_dump(
        by_alias=True, mode="json",
    )


def _note_payload(note: Note) -> dict[str, object]:
    return NoteDetail.model_validate(note, from_attributes=True).model_dump(
        by_alias=True, mode="json",
    )


def _require_context(
    ctx: RunContext[AgentDeps],
) -> tuple[DBSessionFactory, UUID] | None:
    """Return ``(factory, conversation_id)`` or ``None`` if unavailable.

    ``None`` means the scratchpad can't be reached (missing DB or
    conversation id). Callers must surface that to the model as a plain
    tool-result string — a ``ModelRetry`` here would just loop the model
    against a permanent condition.
    """
    factory = ctx.deps.db_session_factory
    conversation_id = ctx.deps.conversation_id
    if factory is None or conversation_id is None:
        return None
    return factory, conversation_id


def _not_found_msg(note_id: str) -> str:
    return f"note id {note_id!r} not found — call list_notes() to see current notes"


async def note(
    ctx: RunContext[AgentDeps],
    title: str,
    summary: str,
    body: str,
    tags: list[str] | None = None,
    pinned: bool = False,
) -> ToolReturn[dict[str, object]]:
    """Save a scratchpad note.

    Use liberally: before moving on from any promising search, save what you
    learned. Over-noting is cheaper than re-discovering.
    """
    ctx_or_none = _require_context(ctx)
    if ctx_or_none is None:
        return ToolReturn(return_value={"error": _MSG_MISSING_CTX})
    factory, conversation_id = ctx_or_none
    try:
        data = (
            NoteCreate(title=title, summary=summary, body=body, pinned=pinned)
            if tags is None
            else NoteCreate(
                title=title,
                summary=summary,
                body=body,
                pinned=pinned,
                tags=tags,
            )
        )
    except ValidationError as exc:
        msg = f"invalid note payload: {exc}"
        raise ModelRetry(msg) from exc

    async with factory() as session:
        repo = ScratchpadRepository(session)
        created = await repo.create(conversation_id=conversation_id, data=data)
        await session.commit()

    logger.info(
        "scratchpad.note_created",
        conversation_id=str(conversation_id),
        note_id=created.id,
        title=created.title,
    )
    return ToolReturn(
        return_value=_ref_payload(created),
        metadata=[scratchpad_updated_event()],
    )


async def update_note(
    ctx: RunContext[AgentDeps],
    note_id: str,
    *,
    title: str | None = None,
    summary: str | None = None,
    body: str | None = None,
    tags: list[str] | None = None,
) -> ToolReturn[dict[str, object]]:
    """Update fields on an existing note. Omitted fields are unchanged."""
    ctx_or_none = _require_context(ctx)
    if ctx_or_none is None:
        return ToolReturn(return_value={"error": _MSG_MISSING_CTX})
    factory, conversation_id = ctx_or_none
    try:
        patch = NoteUpdate(title=title, summary=summary, body=body, tags=tags)
    except ValidationError as exc:
        msg = f"invalid update payload: {exc}"
        raise ModelRetry(msg) from exc

    async with factory() as session:
        repo = ScratchpadRepository(session)
        try:
            updated = await repo.update(
                conversation_id=conversation_id, note_id=note_id, patch=patch,
            )
        except LookupError as exc:
            raise ModelRetry(_not_found_msg(note_id)) from exc
        await session.commit()

    return ToolReturn(
        return_value=_ref_payload(updated),
        metadata=[scratchpad_updated_event()],
    )


async def delete_note(
    ctx: RunContext[AgentDeps], note_id: str,
) -> ToolReturn[str]:
    """Remove a note. Use when the note is superseded by a newer one."""
    ctx_or_none = _require_context(ctx)
    if ctx_or_none is None:
        return ToolReturn(return_value=_MSG_MISSING_CTX)
    factory, conversation_id = ctx_or_none
    async with factory() as session:
        repo = ScratchpadRepository(session)
        ok = await repo.delete(conversation_id=conversation_id, note_id=note_id)
        if not ok:
            raise ModelRetry(_not_found_msg(note_id))
        await session.commit()
    return ToolReturn(
        return_value="deleted", metadata=[scratchpad_updated_event()],
    )


async def pin_note(
    ctx: RunContext[AgentDeps], note_id: str,
) -> ToolReturn[dict[str, object]]:
    """Pin a note so compaction never merges or drops it."""
    ctx_or_none = _require_context(ctx)
    if ctx_or_none is None:
        return ToolReturn(return_value={"error": _MSG_MISSING_CTX})
    factory, conversation_id = ctx_or_none
    async with factory() as session:
        repo = ScratchpadRepository(session)
        try:
            updated = await repo.set_pinned(
                conversation_id=conversation_id, note_id=note_id, pinned=True,
            )
        except LookupError as exc:
            raise ModelRetry(_not_found_msg(note_id)) from exc
        await session.commit()
    return ToolReturn(
        return_value=_ref_payload(updated), metadata=[scratchpad_updated_event()],
    )


async def unpin_note(
    ctx: RunContext[AgentDeps], note_id: str,
) -> ToolReturn[dict[str, object]]:
    """Unpin a previously pinned note."""
    ctx_or_none = _require_context(ctx)
    if ctx_or_none is None:
        return ToolReturn(return_value={"error": _MSG_MISSING_CTX})
    factory, conversation_id = ctx_or_none
    async with factory() as session:
        repo = ScratchpadRepository(session)
        try:
            updated = await repo.set_pinned(
                conversation_id=conversation_id, note_id=note_id, pinned=False,
            )
        except LookupError as exc:
            raise ModelRetry(_not_found_msg(note_id)) from exc
        await session.commit()
    return ToolReturn(
        return_value=_ref_payload(updated), metadata=[scratchpad_updated_event()],
    )


def _filter_description(
    tag: str | None, pinned: bool | None,
) -> str:
    parts: list[str] = []
    if tag is not None:
        parts.append(f"tag='{tag}'")
    if pinned is True:
        parts.append("pinned=true")
    if pinned is False:
        parts.append("pinned=false")
    return f" with {' and '.join(parts)}" if parts else ""


async def list_notes(
    ctx: RunContext[AgentDeps],
    tag: str | None = None,
    pinned: bool | None = None,
    limit: int = 50,
) -> dict[str, object]:
    """List notes (refs only, no body). Optional tag/pinned filter.

    Returns an envelope ``{totalNotes, matches, summary}``. ``totalNotes`` is
    the size of the whole scratchpad — distinguish "no matches" from "empty
    scratchpad" via that field.
    """
    ctx_or_none = _require_context(ctx)
    if ctx_or_none is None:
        return {"error": _MSG_MISSING_CTX, "totalNotes": 0, "matches": []}
    factory, conversation_id = ctx_or_none
    async with factory() as session:
        repo = ScratchpadRepository(session)
        notes = await repo.list_notes(
            conversation_id=conversation_id, tag=tag, pinned=pinned, limit=limit,
        )
        total, _ = await repo.totals(conversation_id=conversation_id)

    matches = [_ref_payload(n) for n in notes]
    filter_desc = _filter_description(tag, pinned)
    if total == 0:
        summary = "No notes saved in this scratchpad yet."
    elif not matches:
        summary = f"No notes{filter_desc} (scratchpad has {total} notes total)."
    else:
        summary = f"{len(matches)} of {total} notes{filter_desc}."
    return {"totalNotes": total, "matches": matches, "summary": summary}


async def search_notes(
    ctx: RunContext[AgentDeps], query: str, limit: int = 10,
) -> dict[str, object]:
    """Keyword/phrase search across title + summary + body via Postgres FTS.

    Returns an envelope ``{totalNotes, query, matches, summary}``. An empty
    ``matches`` with ``totalNotes > 0`` means the query didn't hit; with
    ``totalNotes == 0`` it means the scratchpad is empty.
    """
    ctx_or_none = _require_context(ctx)
    if ctx_or_none is None:
        return {
            "error": _MSG_MISSING_CTX,
            "totalNotes": 0,
            "query": query,
            "matches": [],
        }
    factory, conversation_id = ctx_or_none
    async with factory() as session:
        repo = ScratchpadRepository(session)
        hits = await repo.search_notes(
            conversation_id=conversation_id, query=query, limit=limit,
        )
        total, _ = await repo.totals(conversation_id=conversation_id)

    matches = [_ref_payload(n) for n in hits]
    if total == 0:
        summary = "No notes saved in this scratchpad yet."
    elif not matches:
        summary = (
            f"No notes match {query!r} "
            f"(scratchpad has {total} notes total — try list_notes to browse)."
        )
    else:
        summary = f"{len(matches)} of {total} notes matched {query!r}."
    return {
        "totalNotes": total,
        "query": query,
        "matches": matches,
        "summary": summary,
    }


async def read_note(
    ctx: RunContext[AgentDeps], note_id: str,
) -> dict[str, object]:
    """Fetch the full note (including body) by id."""
    ctx_or_none = _require_context(ctx)
    if ctx_or_none is None:
        return {"error": _MSG_MISSING_CTX}
    factory, conversation_id = ctx_or_none
    async with factory() as session:
        repo = ScratchpadRepository(session)
        note_row = await repo.get(conversation_id=conversation_id, note_id=note_id)
    if note_row is None:
        raise ModelRetry(_not_found_msg(note_id))
    return _note_payload(note_row)


async def promote_to_memory(
    ctx: RunContext[AgentDeps],
    note_id: str,
) -> str:
    """Promote a scratchpad note to the user's long-term ``knowledge`` memory.

    Use when a note captures reusable biological knowledge that is worth
    remembering beyond this conversation — a mechanism, a named marker set, a
    fact about an organism. The note's ``title`` / ``summary`` / ``body`` map
    one-to-one onto the knowledge memory's ``name`` / ``summary`` /
    ``content.body``.

    Other memory kinds (``gene_set``, ``strategy``, ``preference``) have
    structured per-kind content schemas and are written automatically by the
    pipeline at the end of successful turns, not via this tool. The
    scratchpad note stays in place; a new cross-thread memory is created.
    """
    ctx_or_none = _require_context(ctx)
    if ctx_or_none is None:
        return _MSG_MISSING_CTX
    factory, conversation_id = ctx_or_none
    store_raw = ctx.deps.memory_store
    user_id = ctx.deps.user_id
    if store_raw is None or user_id is None:
        raise ModelRetry(_MSG_MEMORY_UNAVAILABLE)

    async with factory() as session:
        repo = ScratchpadRepository(session)
        note_row = await repo.get(conversation_id=conversation_id, note_id=note_id)
    if note_row is None:
        raise ModelRetry(_not_found_msg(note_id))

    value = MemoryValue(
        kind="knowledge",
        name=note_row.title,
        summary=note_row.summary,
        tags=list(note_row.tags),
        site_id=ctx.deps.site_id,
        content={"body": note_row.body, "source_note_id": note_row.id},
        auto_retrieve=True,
        source_conversation_id=conversation_id,
        created_at=datetime.now(UTC),
    )
    mem_store = MemoryStore(store=store_raw)
    return await mem_store.put(user_id=user_id, value=value)


_EMPTY_SCRATCHPAD_HIDDEN = frozenset({
    "list_notes",
    "search_notes",
    "read_note",
    "update_note",
    "delete_note",
    "pin_note",
    "unpin_note",
    "promote_to_memory",
})

_SCRATCHPAD_READ_TOOLS = frozenset({"search_notes", "list_notes", "read_note"})

_MAX_CONSECUTIVE_READ = 2


def _loop_hidden_read_tools(ctx: RunContext[AgentDeps]) -> frozenset[str]:
    """Names of scratchpad read tools that should disappear this step
    because the agent called one of them twice in a row. Hiding forces the
    model to take a different action (``note``, ``web_search``, etc.)
    before searching again. Only the TAIL of history matters: any non-read
    tool (mutation or otherwise) breaks the streak and resets.
    """
    counts: dict[str, int] = {}
    for msg in reversed(ctx.messages):
        if not isinstance(msg, ModelResponse):
            continue
        for part in reversed(msg.parts):
            if not isinstance(part, ToolCallPart):
                continue
            if part.tool_name in _SCRATCHPAD_READ_TOOLS:
                counts[part.tool_name] = counts.get(part.tool_name, 0) + 1
                continue
            # Any other tool (mutation or unrelated) ends the read streak.
            return frozenset({n for n, c in counts.items() if c >= _MAX_CONSECUTIVE_READ})
    return frozenset({n for n, c in counts.items() if c >= _MAX_CONSECUTIVE_READ})


async def _prepare_scratchpad_tools(
    ctx: RunContext[AgentDeps],
    tool_defs: list[ToolDefinition],
) -> list[ToolDefinition]:
    factory = ctx.deps.db_session_factory
    conversation_id = ctx.deps.conversation_id
    if factory is None or conversation_id is None:
        return tool_defs
    async with factory() as session:
        repo = ScratchpadRepository(session)
        total, _ = await repo.totals(conversation_id=conversation_id)
    if total == 0:
        return [td for td in tool_defs if td.name not in _EMPTY_SCRATCHPAD_HIDDEN]
    loop_hidden = _loop_hidden_read_tools(ctx)
    if not loop_hidden:
        return tool_defs
    return [td for td in tool_defs if td.name not in loop_hidden]


def build_scratchpad_toolset() -> AbstractToolset[AgentDeps]:
    base = FunctionToolset[AgentDeps](
        tools=[
            note,
            update_note,
            delete_note,
            pin_note,
            unpin_note,
            list_notes,
            search_notes,
            read_note,
            promote_to_memory,
        ],
    )
    return PreparedToolset(wrapped=base, prepare_func=_prepare_scratchpad_tools)

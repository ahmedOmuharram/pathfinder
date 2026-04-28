"""Fork a conversation at a chosen assistant message.

Carries: messages prefix, strategy_ast (minus wdk step ids), step_count,
pipeline, experiment_id, gene_set_id, scratchpad notes, checkpoint state.
Drops: wdk_strategy_id, is_saved, estimated_size, specialist_mode.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import asc, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.scratchpad.repository import ScratchpadRepository
from pathfinder.persistence.models import Conversation, Message

# Persisted ``messages.parts`` entries whose ``type`` matches one of these
# carry scratchpad note ids in their ``input`` and/or ``output`` payloads.
# When forking, we copy scratchpad rows with fresh ids; every reference
# baked into the copied parts needs to be rewritten so the frontend (and any
# later message-history replay) points at the new rows, not the source's.
_SCRATCHPAD_TOOL_PART_TYPES = frozenset({
    "tool-note",
    "tool-update_note",
    "tool-delete_note",
    "tool-pin_note",
    "tool-unpin_note",
    "tool-read_note",
    "tool-promote_to_memory",
    "tool-list_notes",
    "tool-search_notes",
})


class ForkError(ValueError):
    """Raised when the fork request references missing or unauthorized rows."""


async def _copy_checkpoint_state(
    session: AsyncSession,
    *,
    source_thread_id: str,
    new_thread_id: str,
    cutoff_ts: datetime | None,
) -> None:
    """Duplicate LangGraph checkpoint rows up through the fork point.

    Without this, a forked conversation starts with empty ``message_history``
    and the supervisor has no idea what turns preceded the fork.

    ``cutoff_ts`` is the ``created_at`` of the message immediately following
    the fork anchor in the source. Every checkpoint whose ``ts`` is strictly
    earlier than ``cutoff_ts`` belongs to turns up to and including the
    anchor turn; copy only those so LangGraph's "latest" checkpoint in the
    new thread is exactly the moment after the anchor message was persisted.
    When ``cutoff_ts`` is ``None``, the anchor is the latest message, so the
    cutoff is treated as ``+infinity`` and every checkpoint is copied.

    Blobs are keyed by (thread_id, ns, channel, version); we copy the full
    source-thread blob set rather than filtering. Unreferenced blobs in the
    new thread are harmless — they aren't read by any surviving checkpoint.
    Filtering would require parsing every surviving checkpoint's
    ``channel_versions`` to enumerate referenced blobs; not worth the
    complexity for a few kilobytes of orphaned data.

    Writes are scoped to surviving ``checkpoint_id`` values.
    """
    params = {
        "src": source_thread_id,
        "dst": new_thread_id,
        "cutoff": cutoff_ts,
    }
    await session.execute(
        text(
            """
            INSERT INTO checkpoints (
                thread_id, checkpoint_ns, checkpoint_id,
                parent_checkpoint_id, type, checkpoint, metadata
            )
            SELECT
                :dst, checkpoint_ns, checkpoint_id, parent_checkpoint_id,
                type, checkpoint, metadata
            FROM checkpoints
            WHERE thread_id = :src
              AND (checkpoint->>'ts')::timestamptz
                  < COALESCE(CAST(:cutoff AS timestamptz), 'infinity'::timestamptz)
            """,
        ),
        params,
    )
    await session.execute(
        text(
            """
            INSERT INTO checkpoint_blobs (
                thread_id, checkpoint_ns, channel, version, type, blob
            )
            SELECT :dst, checkpoint_ns, channel, version, type, blob
            FROM checkpoint_blobs
            WHERE thread_id = :src
            """,
        ),
        {"src": source_thread_id, "dst": new_thread_id},
    )
    await session.execute(
        text(
            """
            INSERT INTO checkpoint_writes (
                thread_id, checkpoint_ns, checkpoint_id, task_id, idx,
                channel, type, blob, task_path
            )
            SELECT
                :dst, w.checkpoint_ns, w.checkpoint_id, w.task_id, w.idx,
                w.channel, w.type, w.blob, w.task_path
            FROM checkpoint_writes w
            JOIN checkpoints c
              ON c.thread_id = w.thread_id
             AND c.checkpoint_ns = w.checkpoint_ns
             AND c.checkpoint_id = w.checkpoint_id
            WHERE w.thread_id = :src
              AND (c.checkpoint->>'ts')::timestamptz
                  < COALESCE(CAST(:cutoff AS timestamptz), 'infinity'::timestamptz)
            """,
        ),
        params,
    )


def _rewrite_note_ids_in_payload(
    payload: Any, id_map: dict[str, str],
) -> Any:
    """Recursively swap scratchpad note ids inside a JSON-like payload.

    Only values at keys ``id`` / ``noteId`` / ``sourceNoteId`` (and their
    snake_case equivalents) are considered — hitting every string indiscrimi-
    nately would risk corrupting unrelated ids that happen to match the
    ``n-<hex>`` pattern.
    """
    note_id_keys = {"id", "noteId", "note_id", "sourceNoteId", "source_note_id"}
    if isinstance(payload, dict):
        rewritten: dict[str, Any] = {}
        for key, value in payload.items():
            if (
                key in note_id_keys
                and isinstance(value, str)
                and value in id_map
            ):
                rewritten[key] = id_map[value]
            else:
                rewritten[key] = _rewrite_note_ids_in_payload(value, id_map)
        return rewritten
    if isinstance(payload, list):
        return [_rewrite_note_ids_in_payload(item, id_map) for item in payload]
    return payload


def _rewrite_scratchpad_ids_in_parts(
    parts: list[dict[str, Any]], id_map: dict[str, str],
) -> list[dict[str, Any]]:
    """Walk persisted message parts; rewrite scratchpad ids where present.

    Only touches parts whose ``type`` is a scratchpad tool-call/return. Other
    parts pass through unchanged.
    """
    if not id_map:
        return parts
    result: list[dict[str, Any]] = []
    for part in parts:
        part_type = part.get("type")
        if (
            isinstance(part_type, str)
            and part_type in _SCRATCHPAD_TOOL_PART_TYPES
        ):
            new_part: dict[str, Any] = dict(part)
            if "input" in new_part:
                new_part["input"] = _rewrite_note_ids_in_payload(
                    new_part["input"], id_map,
                )
            if "output" in new_part:
                new_part["output"] = _rewrite_note_ids_in_payload(
                    new_part["output"], id_map,
                )
            result.append(new_part)
        else:
            result.append(part)
    return result


async def fork_conversation(
    session: AsyncSession,
    *,
    source_conversation_id: UUID,
    from_message_id: UUID,
    user_id: UUID,
    new_name: str | None = None,
) -> Conversation:
    """Create a fork. ``from_message_id`` is the last message copied over."""
    source = await session.scalar(
        select(Conversation).where(Conversation.id == source_conversation_id),
    )
    if source is None or source.user_id != user_id:
        msg = "Source conversation not found"
        raise ForkError(msg)

    anchor = await session.scalar(
        select(Message).where(
            Message.id == from_message_id,
            Message.conversation_id == source_conversation_id,
        ),
    )
    if anchor is None:
        msg = "Fork anchor message not found in source conversation"
        raise ForkError(msg)

    prefix_rows = await session.scalars(
        select(Message)
        .where(
            Message.conversation_id == source_conversation_id,
            Message.created_at <= anchor.created_at,
        )
        .order_by(asc(Message.created_at)),
    )
    prefix = list(prefix_rows)

    next_message_ts = await session.scalar(
        select(Message.created_at)
        .where(
            Message.conversation_id == source_conversation_id,
            Message.created_at > anchor.created_at,
        )
        .order_by(asc(Message.created_at))
        .limit(1),
    )

    forked_ast = dict(source.strategy_ast or {})
    forked_ast.pop("wdkStepIds", None)
    forked_ast.pop("wdk_step_ids", None)

    new_conv_id = uuid4()
    fork = Conversation(
        id=new_conv_id,
        user_id=user_id,
        site_id=source.site_id,
        name=new_name or f"{source.name} (branch)",
        record_type=source.record_type,
        supervisor_model_id=source.supervisor_model_id,
        parent_conversation_id=source_conversation_id,
        parent_message_id=from_message_id,
        strategy_ast=forked_ast,
        step_count=source.step_count,
        pipeline=dict(source.pipeline) if source.pipeline is not None else None,
        gene_set_id=source.gene_set_id,
        gene_set_auto_imported=source.gene_set_auto_imported,
        experiment_id=source.experiment_id,
        specialist_mode=None,
    )
    session.add(fork)
    await session.flush()

    # Copy scratchpad rows under the fork with fresh ids. We must do this
    # before copying messages so the id_map is ready for rewriting persisted
    # tool-call parts (see ``_rewrite_scratchpad_ids_in_parts``). The agent
    # no longer sees the source's ids on a resumed run — but the LangGraph
    # checkpoint blobs (which also hold message history) are NOT rewritten;
    # doing so safely would require decoding LangGraph's msgpack-serialized
    # ModelMessage objects and re-encoding them, and the frame can shift
    # with pydantic-ai versions. Stale ids reaching the agent via replay
    # are recoverable: each scratchpad tool raises ``ModelRetry`` with an
    # actionable "note id 'n-...' not found — call list_notes()" message,
    # so the agent reorients on next call. User-visible ``messages.parts``
    # IS rewritten so the chat UI never shows dangling ids.
    scratchpad_repo = ScratchpadRepository(session)
    id_map = await scratchpad_repo.copy_notes_for_fork(
        source_conversation_id=source_conversation_id,
        target_conversation_id=new_conv_id,
    )

    for src_msg in prefix:
        rewritten_parts = _rewrite_scratchpad_ids_in_parts(
            list(src_msg.parts), id_map,
        )
        session.add(
            Message(
                id=uuid4(),
                conversation_id=new_conv_id,
                role=src_msg.role,
                parts=rewritten_parts,
                metadata_=dict(src_msg.metadata_ or {}),
            ),
        )

    await session.flush()
    await _copy_checkpoint_state(
        session,
        source_thread_id=str(source_conversation_id),
        new_thread_id=str(new_conv_id),
        cutoff_ts=next_message_ts,
    )
    return fork

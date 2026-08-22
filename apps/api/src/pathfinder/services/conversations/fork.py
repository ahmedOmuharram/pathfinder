from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import asc, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pathfinder.integrations.veupathdb.factory import get_strategy_api
from pathfinder.integrations.veupathdb.wdk_models import WDKStepTree
from pathfinder.persistence.models import (
    Conversation,
    ConversationStrategy,
    Message,
)
from pathfinder.persistence.repositories.scratchpad import ScratchpadRepository
from pathfinder.platform.errors import AppError
from pathfinder.platform.logging import get_logger
from pathfinder.services.conversations.authz import owned_by_caller

logger = get_logger(__name__)

_SCRATCHPAD_TOOL_PART_TYPES = frozenset(
    {
        "tool-note",
        "tool-update_note",
        "tool-delete_note",
        "tool-pin_note",
        "tool-unpin_note",
        "tool-read_note",
        "tool-promote_to_memory",
        "tool-list_notes",
        "tool-search_notes",
    }
)


class ForkError(ValueError):
    """Raised when the fork request references missing or unauthorized rows."""


async def _copy_conversation_events(
    session: AsyncSession,
    *,
    source_conversation_id: UUID,
    new_conversation_id: UUID,
    cutoff_ts: datetime | None,
    id_map: dict[str, str],
) -> None:
    rows = await session.execute(
        text(
            """
            SELECT id, turn_id, task_id, chunk
            FROM conversation_events
            WHERE conversation_id = :src
              AND emitted_at
                  < COALESCE(CAST(:cutoff AS timestamptz), 'infinity'::timestamptz)
            ORDER BY id ASC
            """,
        ),
        {"src": str(source_conversation_id), "cutoff": cutoff_ts},
    )
    inserts: list[dict[str, Any]] = []
    for row in rows.mappings():
        chunk = _rewrite_scratchpad_ids_in_chunk(dict(row["chunk"]), id_map)
        inserts.append(
            {
                "conversation_id": str(new_conversation_id),
                "turn_id": str(row["turn_id"]) if row["turn_id"] is not None else None,
                "task_id": str(row["task_id"]) if row["task_id"] is not None else None,
                "chunk": chunk,
            }
        )
    if not inserts:
        return
    await session.execute(
        text(
            """
            INSERT INTO conversation_events (
                conversation_id, turn_id, task_id, chunk
            )
            VALUES (
                CAST(:conversation_id AS uuid),
                CAST(:turn_id AS uuid),
                CAST(:task_id AS uuid),
                CAST(:chunk AS jsonb)
            )
            """,
        ),
        [{**ins, "chunk": json.dumps(ins["chunk"])} for ins in inserts],
    )


def _rewrite_scratchpad_ids_in_chunk(
    chunk: dict[str, Any],
    id_map: dict[str, str],
) -> dict[str, Any]:
    if not id_map:
        return chunk
    chunk_type = chunk.get("type")
    if isinstance(chunk_type, str) and chunk_type in _SCRATCHPAD_TOOL_PART_TYPES:
        rewritten = dict(chunk)
        if "input" in rewritten:
            rewritten["input"] = _rewrite_note_ids_in_payload(
                rewritten["input"],
                id_map,
            )
        if "output" in rewritten:
            rewritten["output"] = _rewrite_note_ids_in_payload(
                rewritten["output"],
                id_map,
            )
        return rewritten
    if chunk_type == "user-message":
        message = chunk.get("message")
        if isinstance(message, dict):
            rewritten_msg = dict(message)
            parts = rewritten_msg.get("parts")
            if isinstance(parts, list):
                rewritten_msg["parts"] = [
                    _rewrite_note_ids_in_payload(p, id_map) for p in parts
                ]
            return {**chunk, "message": rewritten_msg}
    return chunk


async def _copy_checkpoint_state(
    session: AsyncSession,
    *,
    source_thread_id: str,
    new_thread_id: str,
    cutoff_ts: datetime | None,
) -> None:
    """Copy the LangGraph checkpoint rows that precede the fork point.

    A ``cutoff_ts`` of ``None`` means the anchor is the latest message, so
    every checkpoint is copied. Blobs are copied whole; extra blobs are inert.
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
    payload: Any,
    id_map: dict[str, str],
) -> Any:
    """Swap scratchpad note ids inside a JSON-like payload.

    Only values at known note-id keys are rewritten.
    """
    note_id_keys = {"id", "noteId", "note_id", "sourceNoteId", "source_note_id"}
    if isinstance(payload, dict):
        rewritten: dict[str, Any] = {}
        for key, value in payload.items():
            if key in note_id_keys and isinstance(value, str) and value in id_map:
                rewritten[key] = id_map[value]
            else:
                rewritten[key] = _rewrite_note_ids_in_payload(value, id_map)
        return rewritten
    if isinstance(payload, list):
        return [_rewrite_note_ids_in_payload(item, id_map) for item in payload]
    return payload


def _walk_step_tree_dfs(tree: WDKStepTree) -> list[int]:
    """Return the wdk step ids in pre-order.

    A WDK copy keeps the topology, so the same order pairs old ids to new ids.
    """
    out: list[int] = []
    stack: list[WDKStepTree] = [tree]
    while stack:
        node = stack.pop()
        out.append(node.step_id)
        if node.secondary_input is not None:
            stack.append(node.secondary_input)
        if node.primary_input is not None:
            stack.append(node.primary_input)
    return out


def _remap_wdk_step_ids(
    old_ids: dict[str, int],
    old_tree: WDKStepTree,
    new_tree: WDKStepTree,
) -> dict[str, int]:
    """Map each local id to its new wdk step id by pairing traversal order."""
    old_seq = _walk_step_tree_dfs(old_tree)
    new_seq = _walk_step_tree_dfs(new_tree)
    if len(old_seq) != len(new_seq):
        msg = (
            "fork: source step tree has "
            f"{len(old_seq)} steps but copy has {len(new_seq)}"
        )
        raise ForkError(msg)
    pairing = dict(zip(old_seq, new_seq, strict=True))
    return {
        local_id: pairing[old_wdk_id]
        for local_id, old_wdk_id in old_ids.items()
        if old_wdk_id in pairing
    }


async def _duplicate_wdk_strategy(
    *,
    site_id: str,
    source_wdk_strategy_id: int,
    forked_ast: dict[str, Any],
) -> int | None:
    """Copy the source WDK strategy and remap the AST step ids.

    A return of ``None`` means the fork starts without a WDK strategy.
    """
    api = get_strategy_api(site_id)
    try:
        source = await api.get_strategy(source_wdk_strategy_id)
        identifier = await api.copy_strategy(source.signature)
        copied = await api.get_strategy(identifier.id)
    except AppError as exc:
        logger.warning(
            "fork: WDK strategy duplication failed; fork starts without a WDK strategy",
            source_wdk_strategy_id=source_wdk_strategy_id,
            error=str(exc),
        )
        return None
    old_ids = forked_ast.get("wdkStepIds") or forked_ast.get("wdk_step_ids")
    if isinstance(old_ids, dict):
        new_ids = _remap_wdk_step_ids(
            {k: int(v) for k, v in old_ids.items()},
            source.step_tree,
            copied.step_tree,
        )
        forked_ast["wdkStepIds"] = new_ids
        forked_ast.pop("wdk_step_ids", None)
    return identifier.id


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
        select(Conversation)
        .where(Conversation.id == source_conversation_id)
        .options(selectinload(Conversation.strategy)),
    )
    if source is None or not owned_by_caller(source, user_id):
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

    source_strategy = source.strategy_view
    forked_ast = dict(source_strategy.strategy_ast)
    new_wdk_strategy_id: int | None = None
    if source_strategy.wdk_strategy_id is not None:
        new_wdk_strategy_id = await _duplicate_wdk_strategy(
            site_id=source.site_id,
            source_wdk_strategy_id=source_strategy.wdk_strategy_id,
            forked_ast=forked_ast,
        )
    if new_wdk_strategy_id is None:
        forked_ast.pop("wdkStepIds", None)
        forked_ast.pop("wdk_step_ids", None)

    new_conv_id = uuid4()
    fork = Conversation(
        id=new_conv_id,
        user_id=user_id,
        site_id=source.site_id,
        name=new_name or f"{source.name} (branch)",
        parent_conversation_id=source_conversation_id,
        parent_message_id=from_message_id,
    )
    session.add(fork)
    await session.flush()
    if source.strategy is not None:
        session.add(
            ConversationStrategy(
                conversation_id=new_conv_id,
                record_type=source_strategy.record_type,
                strategy_ast=forked_ast,
                step_count=source_strategy.step_count,
                gene_set_id=source_strategy.gene_set_id,
                gene_set_auto_imported=source_strategy.gene_set_auto_imported,
                experiment_id=source_strategy.experiment_id,
                wdk_strategy_id=new_wdk_strategy_id,
                # The fork still embeds the imported subtrees, so it keeps
                # the references.
                imported_saved_strategy_ids=list(
                    source_strategy.imported_saved_strategy_ids,
                ),
            ),
        )
        await session.flush()

    # Notes copy first so the id map is ready when the chunk copy rewrites
    # tool-call payloads. Checkpoint blobs keep the source note ids.
    scratchpad_repo = ScratchpadRepository(session)
    id_map = await scratchpad_repo.copy_notes_for_fork(
        source_conversation_id=source_conversation_id,
        target_conversation_id=new_conv_id,
    )

    # Each copy keeps its source created_at, because revert cuts on that value.
    for src_msg in prefix:
        session.add(
            Message(
                id=uuid4(),
                conversation_id=new_conv_id,
                role=src_msg.role,
                metadata_=dict(src_msg.metadata_ or {}),
                created_at=src_msg.created_at,
            ),
        )

    await session.flush()
    await _copy_conversation_events(
        session,
        source_conversation_id=source_conversation_id,
        new_conversation_id=new_conv_id,
        cutoff_ts=next_message_ts,
        id_map=id_map,
    )
    await _copy_checkpoint_state(
        session,
        source_thread_id=str(source_conversation_id),
        new_thread_id=str(new_conv_id),
        cutoff_ts=next_message_ts,
    )
    return fork

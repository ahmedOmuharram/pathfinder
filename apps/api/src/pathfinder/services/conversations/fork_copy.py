from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.services.conversations.fork_ids import (
    IdMint,
    rewrite_message_ids_in_chunk,
    rewrite_scratchpad_ids_in_chunk,
)


async def copy_conversation_events(
    session: AsyncSession,
    *,
    source_conversation_id: UUID,
    new_conversation_id: UUID,
    cutoff_ts: datetime | None,
    note_id_map: dict[str, str],
    messages: IdMint,
) -> None:
    rows = await session.execute(
        text(
            """
            SELECT id, turn_id, chunk, emitted_at
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
        chunk = rewrite_scratchpad_ids_in_chunk(dict(row["chunk"]), note_id_map)
        chunk = rewrite_message_ids_in_chunk(chunk, messages)
        inserts.append(
            {
                "conversation_id": str(new_conversation_id),
                "turn_id": (
                    messages.of(str(row["turn_id"]))
                    if row["turn_id"] is not None
                    else None
                ),
                # The tag names the parent's task row, whose delete cascades.
                # A fork's log outlives every operation on its parent.
                "task_id": None,
                "chunk": chunk,
                # Each copy keeps its source time, because revert cuts on it.
                "emitted_at": row["emitted_at"],
            }
        )
    if not inserts:
        return
    await session.execute(
        text(
            """
            INSERT INTO conversation_events (
                conversation_id, turn_id, task_id, chunk, emitted_at
            )
            VALUES (
                CAST(:conversation_id AS uuid),
                CAST(:turn_id AS uuid),
                CAST(:task_id AS uuid),
                CAST(:chunk AS jsonb),
                CAST(:emitted_at AS timestamptz)
            )
            """,
        ),
        [{**ins, "chunk": json.dumps(ins["chunk"])} for ins in inserts],
    )


async def copy_checkpoint_state(
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

"""Turn-level persistence + memory retrieval for the Lead node.

Memory retrieval at turn start and the assistant-message write at turn end,
plus the message metadata builder they share.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from langgraph.runtime import Runtime

from pathfinder.ai.conversation.event_stream import fetch_chunks_after
from pathfinder.ai.conversation.ui_message_reducer import reduce_chunks
from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.memory.retrieval import retrieve_relevant_memories
from pathfinder.ai.memory.store import MemoryStore, StoredMemory
from pathfinder.persistence.repositories import MessagesRepository
from pathfinder.persistence.repositories._message_metadata import MessageMetadata


def _build_metadata(
    *,
    state: PipelineState,
    total_tokens: int,
    cost_usd: Decimal,
) -> dict[str, Any]:
    return MessageMetadata.model_validate(
        {
            "traceId": state.turn_trace_id,
            "createdAt": state.turn_created_at,
            "siteId": state.site_id,
            "mode": state.mode,
            "usage": {
                "totalTokens": total_tokens,
                "costUsd": str(cost_usd),
            },
        },
    ).model_dump(by_alias=True, exclude_none=True)


async def retrieve_memories(
    state: PipelineState,
    runtime: Runtime[Context],
) -> list[StoredMemory]:
    """Fresh-turn cross-thread retrieval.

    Returns ``[]`` on an approval-resume turn — the turn's memories are
    already persisted on ``state.retrieved_memories``, so the lead node
    preserves them rather than re-querying (and does not re-emit the
    recalled-memories chunk).
    """
    if state.pending_approval is not None:
        return []
    if runtime.context is None or runtime.context.memory_store is None:
        return []
    if not state.user_prompt.strip():
        return []
    mem_store = MemoryStore(store=runtime.context.memory_store)
    return await retrieve_relevant_memories(
        store=mem_store,
        user_id=state.user_id,
        query=state.user_prompt,
        site_id=state.site_id,
        top_k=8,
    )


async def write_turn_message(
    *,
    context: Context,
    state: PipelineState,
) -> UUID | None:
    """Persist the assistant message after the Lead's run completes."""
    _, chunks = await fetch_chunks_after(
        state.conversation_id,
        state.turn_start_event_id,
    )
    if not chunks:
        return None
    msg = reduce_chunks(chunks, default_message_id=str(state.turn_message_id))
    parts = msg["parts"]
    if not parts:
        return None
    raw_id = msg.get("id") or str(state.turn_message_id)
    message_id = UUID(raw_id)
    metadata = _build_metadata(
        state=state,
        total_tokens=state.turn_total_tokens,
        cost_usd=state.turn_total_cost_usd,
    )
    async with context.db_session_factory() as session:
        await MessagesRepository(session).upsert_message(
            message_id=message_id,
            conversation_id=state.conversation_id,
            role="assistant",
            metadata=metadata,
        )
        await session.commit()
    return message_id

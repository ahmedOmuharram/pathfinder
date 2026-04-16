from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.memory.schemas import MemoryValue
from pathfinder.ai.memory.store import MemoryStore
from pathfinder.ai.memory.tombstones import (
    SessionFactory,
    TombstoneRepository,
    compute_content_hash,
)
from pathfinder.persistence.models import Chat, Message
from pathfinder.persistence.session import async_session_factory

PREFERENCE_MIN_SUCCESSES = 3


async def auto_write_memories(
    *,
    store: MemoryStore,
    tombstones: TombstoneRepository,
    state: PipelineState,
    session_factory: SessionFactory = async_session_factory,
) -> int:
    """Write successful turn artifacts into the user's memory namespaces.

    Called from the supervisor when it routes to ``end`` after verification.
    Deterministic keys so successive turns update rather than duplicate.
    Returns the number of memories written.

    All tombstone checks are batched into a single SELECT so the number of
    DB round-trips is ``O(1)`` regardless of ``len(created_gene_set_ids)``.
    """
    candidates: list[tuple[MemoryValue, str]] = _collect_candidates(state)
    # The preference heuristic runs its DB check separately below so we can
    # include it in the same candidate list when it qualifies.
    if state.site_id:
        has_threshold = await _has_min_successful_verifications(
            user_id=state.user_id,
            session_factory=session_factory,
            threshold=PREFERENCE_MIN_SUCCESSES,
        )
        if has_threshold:
            pref_value = _build_preference_value(state)
            pref_key = f"preferred_site:{state.site_id}"
            candidates.append((pref_value, pref_key))

    if not candidates:
        return 0

    tombstoned = await tombstones.existing_hashes(
        user_id=state.user_id,
        values=[value for value, _key in candidates],
    )
    written = 0
    for value, key in candidates:
        content_hash = compute_content_hash(value.content)
        if (value.kind, content_hash) in tombstoned:
            continue
        await store.put(user_id=state.user_id, value=value, key=key)
        written += 1
    return written


def _collect_candidates(
    state: PipelineState,
) -> list[tuple[MemoryValue, str]]:
    """Synchronous part of candidate enumeration (strategies + gene sets)."""
    candidates: list[tuple[MemoryValue, str]] = []
    if state.active_plan is not None:
        candidates.append((
            _build_strategy_value(state),
            f"strategy:{state.chat_id.hex}",
        ))
    candidates.extend(
        (_build_gene_set_value(state, gs_id), f"gene_set:{gs_id}")
        for gs_id in state.created_gene_set_ids
    )
    return candidates


def _build_strategy_value(state: PipelineState) -> MemoryValue:
    plan = state.active_plan
    if plan is None:
        msg = "_build_strategy_value requires state.active_plan to be set"
        raise ValueError(msg)
    return MemoryValue(
        kind="strategy",
        name=f"chat-{state.chat_id.hex[:8]}",
        summary=_summarize_plan(state),
        tags=_plan_tags(state),
        site_id=state.site_id,
        content={
            "plan": plan.model_dump(mode="json"),
            "problem_frame": (
                state.problem_frame.model_dump(mode="json")
                if state.problem_frame
                else None
            ),
            "user_prompt": state.user_prompt,
        },
        source_chat_id=state.chat_id,
        created_at=datetime.now(UTC),
    )


def _build_gene_set_value(state: PipelineState, gs_id: str) -> MemoryValue:
    return MemoryValue(
        kind="gene_set",
        name=gs_id,
        summary=f"Gene set {gs_id} created in chat-{state.chat_id.hex[:8]}",
        tags=[state.site_id] if state.site_id else [],
        site_id=state.site_id,
        content={"gene_set_id": gs_id},
        source_chat_id=state.chat_id,
        created_at=datetime.now(UTC),
    )


def _build_preference_value(state: PipelineState) -> MemoryValue:
    return MemoryValue(
        kind="preference",
        name=f"preferred_site:{state.site_id}",
        summary=f"Frequently uses {state.site_id}",
        tags=[state.site_id] if state.site_id else [],
        site_id=state.site_id,
        content={"preferred_site": state.site_id},
        source_chat_id=state.chat_id,
        created_at=datetime.now(UTC),
    )


async def _has_min_successful_verifications(
    *,
    user_id: UUID,
    session_factory: SessionFactory,
    threshold: int,
) -> bool:
    """Return True iff the user has ``>= threshold`` successful verifications.

    Uses EXISTS with LIMIT to avoid an unbounded COUNT(*) over the user's full
    message history. The query is O(threshold) rows in the worst case.
    """
    async with session_factory() as session:
        return await _check_verifications_threshold(session, user_id, threshold)


async def _check_verifications_threshold(
    session: AsyncSession, user_id: UUID, threshold: int,
) -> bool:
    inner = (
        select(Message.id)
        .join(Chat, Message.chat_id == Chat.id)
        .where(
            Chat.user_id == user_id,
            Message.role == "assistant",
            Message.metadata_["phase"].as_string() == "verification",
            Message.metadata_["turnCompleted"].as_boolean().is_(True),
        )
        .limit(threshold)
    ).subquery()
    row_count_stmt = select(exists().select_from(
        select(inner.c.id).offset(threshold - 1).subquery()
    ))
    result = await session.execute(row_count_stmt)
    return bool(result.scalar())


def _summarize_plan(state: PipelineState) -> str:
    if state.problem_frame:
        return state.problem_frame.interpreted_goal[:120]
    return state.user_prompt[:120]


def _plan_tags(state: PipelineState) -> list[str]:
    tags = [state.site_id] if state.site_id else []
    if state.problem_frame and state.problem_frame.organism_scope:
        tags.append(state.problem_frame.organism_scope)
    return tags

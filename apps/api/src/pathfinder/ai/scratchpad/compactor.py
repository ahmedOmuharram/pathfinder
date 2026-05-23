from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pathfinder.ai.agents.compactor import (
    CompactionResult,
    CompactorDeps,
    build_compactor_agent,
)
from pathfinder.ai.cost import cost_for_run
from pathfinder.ai.graph.runtime import DBSessionFactory
from pathfinder.ai.scratchpad._ids import approx_body_tokens
from pathfinder.ai.scratchpad.models import CompactionRun, Note, NoteCreate
from pathfinder.ai.scratchpad.repository import ScratchpadRepository
from pathfinder.platform.logging import get_logger

logger = get_logger(__name__)

COMPACT_COUNT_THRESHOLD = 50
COMPACT_TOKENS_THRESHOLD = 10000


def _format_notes_for_compactor(notes: list[Note]) -> str:
    lines: list[str] = []
    for n in notes:
        lines.append(f"### [{n.id}] {n.title}")
        lines.append(f"summary: {n.summary}")
        if n.tags:
            lines.append(f"tags: {', '.join(n.tags)}")
        lines.append("")
        lines.append(n.body)
        lines.append("")
    return "\n".join(lines)


def _enforce_budget(
    new_notes: list[NoteCreate], *, threshold_tokens: int,
) -> list[NoteCreate]:
    """Drop oldest (first) entries until total approx-tokens <= threshold."""
    trimmed = list(new_notes)
    while (
        trimmed
        and sum(approx_body_tokens(n.body) for n in trimmed) > threshold_tokens
    ):
        trimmed.pop(0)
    return trimmed


async def maybe_compact_scratchpad(
    *,
    conversation_id: UUID,
    user_id: UUID,
    db_session_factory: DBSessionFactory,
) -> CompactionRun | None:
    """Run compaction if over budget. Returns None otherwise.

    The gate counts only non-pinned notes via ``compactable_totals``. Pinned
    notes are untouchable, so including them in the gate would cause
    repeated LLM calls that cannot reduce the count — see MAJOR 2 in the
    scratchpad design review.
    """
    del user_id
    async with db_session_factory() as session:
        repo = ScratchpadRepository(session)
        compactable_count, compactable_tokens = await repo.compactable_totals(
            conversation_id=conversation_id,
        )
        total_count, total_tokens = await repo.totals(
            conversation_id=conversation_id,
        )

    over_count = compactable_count > COMPACT_COUNT_THRESHOLD
    over_tokens = compactable_tokens > COMPACT_TOKENS_THRESHOLD
    if not over_count and not over_tokens:
        return None
    reason: Literal["count", "tokens", "both"] = (
        "both" if over_count and over_tokens
        else ("count" if over_count else "tokens")
    )

    async with db_session_factory() as session:
        repo = ScratchpadRepository(session)
        non_pinned = await repo.list_notes(
            conversation_id=conversation_id, pinned=False, limit=1000,
        )

    agent = build_compactor_agent(model_id=None)
    model_id: str | None = None
    deps = CompactorDeps(
        input_notes_markdown=_format_notes_for_compactor(non_pinned),
    )

    try:
        result = await agent.run("Compact the notebook.", deps=deps)
    except Exception:
        # Compaction failure must never break the turn.
        logger.exception(
            "scratchpad compaction failed",
            conversation_id=str(conversation_id),
        )
        return None

    output: CompactionResult = result.output
    trimmed = _enforce_budget(
        output.notes, threshold_tokens=COMPACT_TOKENS_THRESHOLD,
    )

    usage = result.usage()
    response = result.response
    cost = cost_for_run(
        usage=usage,
        model_name=response.model_name,
        provider_name=response.provider_name,
        provider_url=response.provider_url,
    )

    async with db_session_factory() as session:
        repo = ScratchpadRepository(session)
        await repo.replace_non_pinned(
            conversation_id=conversation_id, new_notes=trimmed,
        )
        new_count, new_tokens = await repo.totals(
            conversation_id=conversation_id,
        )
        run = CompactionRun(
            conversation_id=conversation_id,
            triggered_at=datetime.now(UTC),
            before_count=total_count,
            after_count=new_count,
            before_tokens=total_tokens,
            after_tokens=new_tokens,
            model_id=model_id or "",
            cost_usd=cost,
            trigger_reason=reason,
        )
        await repo.log_compaction(run=run)
        await session.commit()

    logger.info(
        "scratchpad compaction completed",
        conversation_id=str(conversation_id),
        before_count=total_count,
        after_count=new_count,
        before_tokens=total_tokens,
        after_tokens=new_tokens,
        trigger_reason=reason,
        model_id=model_id or "",
        cost_usd=str(cost),
    )
    return run

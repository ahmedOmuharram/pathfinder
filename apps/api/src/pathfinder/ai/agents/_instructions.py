"""Pinned instructions any assistant can render: what it knows about the user
and the notes it kept for this conversation."""

from __future__ import annotations

from pydantic_ai.tools import RunContext

from pathfinder.ai.scratchpad.rendering import render_scratchpad_for_phase
from pathfinder.assistant_core.graph.runtime import AssistantDeps
from pathfinder.persistence.repositories.scratchpad import ScratchpadRepository


def pinned_user_memories(ctx: RunContext[AssistantDeps]) -> str | None:
    memories = ctx.deps.retrieved_memories
    if not memories:
        return None
    lines = ["## What you know about this user"]
    for m in memories:
        tags_str = f" [{', '.join(m.tags)}]" if m.tags else ""
        lines.append(f"- [{m.kind}] {m.name}{tags_str}: {m.summary}")
    return "\n".join(lines)


async def pinned_scratchpad(ctx: RunContext[AssistantDeps]) -> str | None:
    """Render the conversation's scratchpad index for the phase agent."""
    if ctx.deps.db_session_factory is None or ctx.deps.conversation_id is None:
        return None
    async with ctx.deps.db_session_factory() as session:
        repo = ScratchpadRepository(session)
        notes, total_count, _ = await repo.list_for_index_with_totals(
            conversation_id=ctx.deps.conversation_id,
        )
    return render_scratchpad_for_phase(notes, total_count=total_count)

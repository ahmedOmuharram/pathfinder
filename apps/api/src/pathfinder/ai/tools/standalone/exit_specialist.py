"""``exit_specialist`` tool — agent-initiated exit from a specialist mode.

Direct DB + memory writes (no interrupt). Clears
``Conversation.specialist_mode`` for the current turn's conversation,
autowrites ``findings`` to the cross-thread Store as ``kind=knowledge``
(subject to tombstone check). The next turn's ``specialist_router``
sees specialist_mode is None and routes to supervisor as usual.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field
from pydantic_ai import RunContext
from pydantic_ai.messages import ToolReturn

from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.memory.autowrite import (
    DraftWriteContext,
    write_drafts_with_tombstones,
)
from pathfinder.ai.memory.schemas import MemoryEntryDraft
from pathfinder.ai.memory.store import MemoryStore
from pathfinder.ai.memory.tombstones import TombstoneRepository
from pathfinder.persistence.repositories.conversation import (
    ConversationRepository,
    ConversationUpdate,
)
from pathfinder.platform.pydantic_base import CamelModel


class ExitSpecialistResult(CamelModel):
    cleared: bool
    autowritten_count: int = 0


async def exit_specialist(
    ctx: RunContext[AgentDeps],
    summary: Annotated[
        str,
        Field(
            min_length=1,
            max_length=2000,
            description=(
                "One-paragraph summary of what was accomplished in the "
                "specialist session. Shown to the user as closing prose."
            ),
        ),
    ],
    findings: Annotated[
        list[MemoryEntryDraft] | None,
        Field(
            default=None,
            max_length=10,
            description=(
                "Stable knowledge worth saving as memory (kind=knowledge). "
                "For /validate failures, include any tagged with "
                "'validate-failure' so they show up in filtering."
            ),
        ),
    ] = None,
) -> ToolReturn[ExitSpecialistResult]:
    """Exit the current specialist mode and return to the main flow.

    Use when:
      - the user's question has been answered,
      - the user explicitly asked to exit,
      - or the conversation has drifted off the specialist's purpose.

    The chat shell renders ``summary`` as prose; ``findings`` are saved
    as kind=knowledge memories (skipping any whose content matches a
    user-deleted tombstone).
    """
    deps = ctx.deps
    autowritten = 0
    if (
        findings
        and deps.memory_store is not None
        and deps.db_session_factory is not None
        and deps.user_id is not None
    ):
        memory_store = MemoryStore(store=deps.memory_store)
        tombstones = TombstoneRepository(
            session_factory=deps.db_session_factory,
        )
        autowritten = await write_drafts_with_tombstones(
            store=memory_store,
            tombstones=tombstones,
            drafts=findings,
            context=DraftWriteContext(
                user_id=deps.user_id,
                site_id=deps.site_id,
                kind="knowledge",
                source_conversation_id=deps.conversation_id,
            ),
        )

    cleared = False
    if (
        deps.db_session_factory is not None
        and deps.conversation_id is not None
    ):
        async with deps.db_session_factory() as session:
            await ConversationRepository(session).update_conversation(
                deps.conversation_id,
                ConversationUpdate(
                    specialist_mode=None,
                    specialist_mode_set=True,
                ),
            )
            await session.commit()
            cleared = True

    _ = summary  # streamed back to the user as prose by the agent itself
    return ToolReturn(
        return_value=ExitSpecialistResult(
            cleared=cleared, autowritten_count=autowritten,
        ),
    )

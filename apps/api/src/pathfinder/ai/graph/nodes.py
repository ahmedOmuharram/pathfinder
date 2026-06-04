from __future__ import annotations

from typing import Literal

from langgraph.config import get_stream_writer
from langgraph.runtime import Runtime
from langgraph.types import Command
from sqlalchemy.exc import SQLAlchemyError

from pathfinder.ai.graph._lead_turn import write_turn_message
from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.graph.stream_events import scratchpad_updated_event
from pathfinder.ai.memory.autowrite import auto_write_memories
from pathfinder.ai.memory.store import MemoryStore
from pathfinder.ai.memory.tombstones import TombstoneRepository
from pathfinder.ai.scratchpad.compactor import maybe_compact_scratchpad
from pathfinder.platform.logging import get_logger

logger = get_logger(__name__)

_END: Literal["__end__"] = "__end__"


async def finalize_turn_node(
    state: PipelineState, runtime: Runtime[Context]
) -> Command[Literal["__end__"]]:
    if runtime.context is not None:
        try:
            await write_turn_message(
                context=runtime.context,
                state=state,
            )
        except SQLAlchemyError:
            logger.warning(
                "failed to write turn message",
                conversation_id=str(state.conversation_id),
            )

    if (
        runtime.context is not None
        and state.verification_digest is not None
        and state.verification_digest.success
        and runtime.context.memory_store is not None
    ):
        mem_store = MemoryStore(store=runtime.context.memory_store)
        tombstones = TombstoneRepository(
            session_factory=runtime.context.db_session_factory,
        )
        try:
            await auto_write_memories(
                store=mem_store,
                tombstones=tombstones,
                state=state,
            )
        except (RuntimeError, ValueError, OSError, SQLAlchemyError) as exc:
            logger.warning("auto-write memories failed: %s", exc)

    if runtime.context is not None and state.verification_digest is not None:
        try:
            compaction_run = await maybe_compact_scratchpad(
                conversation_id=state.conversation_id,
                user_id=state.user_id,
                db_session_factory=runtime.context.db_session_factory,
            )
        except Exception:
            logger.exception(
                "scratchpad compaction wrapper failed",
                conversation_id=str(state.conversation_id),
            )
            compaction_run = None
        if compaction_run is not None:
            writer = get_stream_writer()
            writer(
                {
                    "chunk": scratchpad_updated_event().model_dump(
                        by_alias=True,
                        mode="json",
                        exclude_none=True,
                    ),
                },
            )

    return Command(goto=_END)

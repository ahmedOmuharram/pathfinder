"""The per-turn resources and dependency container the runtime owns."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from uuid import UUID

from langgraph.store.postgres.aio import AsyncPostgresStore
from pydantic import BaseModel, ConfigDict, Field, SkipValidation

from pathfinder.assistant_core.capabilities.repetition_guard import ToolRepetitionGuard
from pathfinder.assistant_core.memory.schemas import MemoryValue
from pathfinder.platform.db import DBSessionFactory
from pathfinder.platform.types import ReasoningEffort


@dataclass(frozen=True, kw_only=True)
class TurnContext:
    # Non-serializable per-turn resources passed via
    # ``graph.astream(..., context=ctx)``; never checkpointed.

    site_id: str
    user_id: UUID
    db_session_factory: DBSessionFactory
    cancel_event: asyncio.Event
    memory_store: AsyncPostgresStore | None = None
    # Keyed by the product's own role names; the runtime never reads them.
    phase_models: dict[str, str] = field(default_factory=dict)
    phase_reasoning: dict[str, ReasoningEffort] = field(default_factory=dict)


class AssistantDeps(BaseModel):
    # Resource fields use ``SkipValidation`` so tests can inject mock
    # instances without tripping Pydantic's isinstance check.

    model_config = ConfigDict(arbitrary_types_allowed=True)

    site_id: str
    user_id: UUID | None = None
    conversation_id: UUID | None = None
    db_session_factory: SkipValidation[DBSessionFactory] | None = None
    memory_store: SkipValidation[AsyncPostgresStore] | None = None
    cancel_event: SkipValidation[asyncio.Event] | None = None
    retrieved_memories: list[MemoryValue] = Field(default_factory=list)
    tool_repetition_guard: ToolRepetitionGuard = Field(
        default_factory=ToolRepetitionGuard,
    )

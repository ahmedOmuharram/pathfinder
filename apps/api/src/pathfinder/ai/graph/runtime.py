from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from langgraph.store.postgres.aio import AsyncPostgresStore
from pydantic import BaseModel, ConfigDict, Field, SkipValidation
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.agents.state import AgentToolState
from pathfinder.ai.capabilities.repetition_guard import ToolRepetitionGuard
from pathfinder.ai.graph.state import (
    PhaseName,
    PhaseOutcome,
    PipelineState,
    ProblemFrame,
)
from pathfinder.ai.memory.schemas import MemoryValue
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService

DBSessionFactory = Callable[[], AsyncSession]


@dataclass(frozen=True)
class Context:
    """Per-invocation runtime context for the LangGraph pipeline.

    Holds non-serializable services and per-chat resources that must NOT be
    checkpointed. Constructed once by the dispatcher per chat turn and passed
    to ``graph.astream(..., context=ctx)``.
    """

    site_id: str
    user_id: UUID
    strategy_session: StrategySession
    db_session_factory: DBSessionFactory
    web_search_service: WebSearchService
    literature_search_service: LiteratureSearchService
    cancel_event: asyncio.Event
    memory_store: AsyncPostgresStore | None = None
    experiment_id: str | None = None


class AgentDeps(BaseModel):
    """Slimmed pydantic-ai per-node deps.

    Built fresh by each node from the current ``PipelineState`` and the
    per-invocation ``Context``. Tools mutate ``problem_frame`` and
    ``agent_state``; the node calls :func:`extract_state_delta` after the
    agent completes to propagate changes back into checkpointed state.

    Service fields use ``SkipValidation`` so tests can inject mock instances
    without failing Pydantic's ``arbitrary_types_allowed`` isinstance check.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    site_id: str
    user_id: UUID | None = None
    strategy_session: SkipValidation[StrategySession] = Field(
        default_factory=lambda: StrategySession(site_id=""),
    )
    web_search_service: SkipValidation[WebSearchService] | None = None
    literature_search_service: SkipValidation[LiteratureSearchService] | None = None
    agent_state: AgentToolState = Field(default_factory=AgentToolState)
    problem_frame: ProblemFrame | None = None
    problem_frame_set_this_run: bool = False
    tool_repetition_guard: ToolRepetitionGuard = Field(
        default_factory=ToolRepetitionGuard,
    )
    experiment_id: str | None = None
    cancel_event: SkipValidation[asyncio.Event] | None = None
    memory_store: SkipValidation[AsyncPostgresStore] | None = None
    retrieved_memories: list[MemoryValue] = Field(default_factory=list)
    conversation_id: UUID | None = None
    db_session_factory: SkipValidation[DBSessionFactory] | None = None
    last_phase_outcome: PhaseOutcome | None = None
    last_phase_name: PhaseName | None = None


def build_node_deps(
    state: PipelineState,
    context: Context,
    *,
    memories: list[MemoryValue] | None = None,
) -> AgentDeps:
    """Construct ``AgentDeps`` for one node invocation."""
    agent_state = AgentToolState(
        discovered_searches=dict(state.discovered_searches),
        active_plan=state.active_plan,
    )
    return AgentDeps(
        site_id=context.site_id,
        user_id=context.user_id,
        strategy_session=context.strategy_session,
        web_search_service=context.web_search_service,
        literature_search_service=context.literature_search_service,
        agent_state=agent_state,
        problem_frame=state.problem_frame,
        experiment_id=context.experiment_id,
        cancel_event=context.cancel_event,
        memory_store=context.memory_store,
        retrieved_memories=memories or [],
        conversation_id=state.conversation_id,
        db_session_factory=context.db_session_factory,
        last_phase_outcome=state.last_phase_outcome,
        last_phase_name=state.current_phase,
    )


def extract_state_delta(deps: AgentDeps) -> dict[str, Any]:
    """Pull mutable scratchpad data out of ``deps`` for state propagation."""
    return {
        "problem_frame": deps.problem_frame,
        "discovered_searches": dict(deps.agent_state.discovered_searches),
        "active_plan": deps.agent_state.active_plan,
    }

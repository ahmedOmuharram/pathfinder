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
    SupervisorEvent,
)
from pathfinder.ai.memory.schemas import MemoryValue
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService

DBSessionFactory = Callable[[], AsyncSession]


@dataclass(frozen=True)
class Context:
    # Non-serializable per-turn resources passed via
    # ``graph.astream(..., context=ctx)``; never checkpointed.

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
    # Service fields use ``SkipValidation`` so tests can inject mock
    # instances without tripping Pydantic's isinstance check.

    model_config = ConfigDict(arbitrary_types_allowed=True)

    site_id: str
    user_id: UUID | None = None
    strategy_session: SkipValidation[StrategySession]
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
    # Specialist mode payload threaded into deps so the validate /
    # research agents' module-level dynamic instructions can read it
    # without registering a new closure per turn (which would leak on
    # the singleton agent).
    specialist_mode: object | None = None
    supervisor_log: list[SupervisorEvent] = Field(default_factory=list)
    writer: SkipValidation[Any] = None


def build_node_deps(
    state: PipelineState,
    context: Context,
    *,
    memories: list[MemoryValue] | None = None,
) -> AgentDeps:
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
        specialist_mode=state.specialist_mode,
        supervisor_log=state.supervisor_log,
    )


def extract_state_delta(deps: AgentDeps) -> dict[str, Any]:
    return {
        "problem_frame": deps.problem_frame,
        "discovered_searches": dict(deps.agent_state.discovered_searches),
        "active_plan": deps.agent_state.active_plan,
    }

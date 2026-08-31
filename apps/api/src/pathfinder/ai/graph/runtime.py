from __future__ import annotations

from dataclasses import dataclass

from assistant_core.capabilities.repetition_guard import ToolRepetitionGuard
from assistant_core.graph.runtime import AssistantDeps, TurnContext
from assistant_core.memory.schemas import MemoryValue
from assistant_core.platform.pydantic_base import CamelModel
from pydantic import Field, SkipValidation

from pathfinder.ai.agents.state import AgentToolState
from pathfinder.ai.agents.tool_vocabulary import build_tool_repetition_guard
from pathfinder.ai.capabilities.service_outage import ServiceOutageMemory
from pathfinder.ai.graph.state import PipelineState
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService
from pathfinder.services.strategies.context import StrategyMutationContext


@dataclass(frozen=True, kw_only=True)
class Context(TurnContext):
    strategy_session: StrategySession
    web_search_service: WebSearchService
    literature_search_service: LiteratureSearchService
    experiment_id: str | None = None


class VerificationScope(CamelModel):
    """What this turn changed, and what the user asked verification to do.

    A fresh turn leaves the counts at zero, which warrants every check.
    """

    criteria_touched: int = 0
    is_edit: bool = False
    enrichment_requested: bool = False

    def warrants_enrichment(self) -> bool:
        """Enrichment costs a background job of minutes, so an edit that
        touched one criterion is verified by its counts instead."""
        if self.enrichment_requested:
            return True
        return not (self.is_edit and self.criteria_touched <= 1)


class AgentDeps(AssistantDeps):
    tool_repetition_guard: ToolRepetitionGuard = Field(
        default_factory=build_tool_repetition_guard,
    )
    strategy_session: SkipValidation[StrategySession]
    web_search_service: SkipValidation[WebSearchService] | None = None
    literature_search_service: SkipValidation[LiteratureSearchService] | None = None
    agent_state: AgentToolState = Field(default_factory=AgentToolState)
    ledger_summary: str = ""
    service_outage: ServiceOutageMemory = Field(default_factory=ServiceOutageMemory)
    experiment_id: str | None = None
    verification_scope: VerificationScope = Field(default_factory=VerificationScope)

    def to_strategy_context(self) -> StrategyMutationContext:
        """Narrow this container down to what strategy-mutation services need."""
        return StrategyMutationContext(
            site_id=self.site_id,
            strategy_session=self.strategy_session,
            conversation_id=self.conversation_id,
            db_session_factory=self.db_session_factory,
        )


def build_node_deps(
    state: PipelineState,
    context: Context,
    *,
    memories: list[MemoryValue] | None = None,
) -> AgentDeps:
    agent_state = AgentToolState(
        discovered_searches=dict(state.domain.discovered_searches),
    )
    return AgentDeps(
        site_id=context.site_id,
        user_id=context.user_id,
        strategy_session=context.strategy_session,
        web_search_service=context.web_search_service,
        literature_search_service=context.literature_search_service,
        agent_state=agent_state,
        experiment_id=context.experiment_id,
        cancel_event=context.cancel_event,
        memory_store=context.memory_store,
        retrieved_memories=memories or [],
        conversation_id=state.conversation_id,
        db_session_factory=context.db_session_factory,
    )

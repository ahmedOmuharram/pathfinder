"""Typed handoff objects between pipeline phases.

Each phase produces a result that the next phase consumes via
``AgentDeps``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from veupath_chatbot.ai.agents.state import SearchOverview
from veupath_chatbot.domain.strategy.plan import StrategyPlan
from veupath_chatbot.platform.types import JSONObject


@dataclass(frozen=True)
class DiscoveryResult:
    """Output of the discovery phase.

    Passed to the planning agent via ``AgentDeps.discovery_result``.
    The planning agent also receives the discovery agent's ``new_messages()``
    as ``message_history`` for full conversational context.
    """

    discovered_searches: dict[str, SearchOverview] = field(default_factory=dict)
    research_notes: str = ""
    intent_summary: str = ""


@dataclass(frozen=True)
class PlanningResult:
    """Output of the planning phase."""

    approved_plan: StrategyPlan | None = None
    questions_answered: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ExecutionResult:
    """Output of the execution phase."""

    wdk_strategy_id: int | None = None
    step_results: dict[str, JSONObject] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class VerificationResult:
    """Output of the verification phase."""

    assessment: str = ""
    sample_record_count: int = 0
    enrichment_ran: bool = False

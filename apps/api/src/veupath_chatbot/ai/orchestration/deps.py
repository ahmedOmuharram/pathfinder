"""Typed dependency injection for pydantic-ai agents.

``AgentDeps`` is passed to every tool via ``RunContext[AgentDeps]`` and to
every dynamic instruction.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from uuid import UUID

from veupath_chatbot.ai.agents.state import AgentToolState
from veupath_chatbot.ai.orchestration.phase_results import (
    DiscoveryResult,
    ExecutionResult,
    PlanningResult,
    VerificationResult,
)
from veupath_chatbot.domain.strategy.session import StrategySession
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.research.literature_search import (
    LiteratureSearchService,
)
from veupath_chatbot.services.research.web_search import WebSearchService


@dataclass
class AgentDeps:
    """Shared dependencies injected into every pydantic-ai tool and instruction.

    Constructed once per turn from persistent state (PostgreSQL, Redis)
    and passed through the pipeline via ``RunContext[AgentDeps]``.
    """

    # --- Core identity ---
    site_id: str
    user_id: UUID | None = None

    # --- Strategy state ---
    strategy_session: StrategySession = field(
        default_factory=lambda: StrategySession(site_id=""),
    )

    # --- Agent state (discovery gate, active plan) ---
    agent_state: AgentToolState = field(default_factory=AgentToolState)

    # --- Research services ---
    web_search_service: WebSearchService | None = None
    literature_search_service: LiteratureSearchService | None = None

    # --- Context ---
    context_summary: str | None = None
    approved_plan: str | None = None
    mentioned_context: str | None = None

    # --- Experiment (workbench) ---
    experiment_id: str | None = None

    # --- Event queue (SSE emission from tools and hooks) ---
    event_queue: asyncio.Queue[JSONObject] | None = None

    # --- Cancellation (long-running optimization) ---
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)

    # --- Phase results (structured handoffs between phases) ---
    discovery_result: DiscoveryResult | None = None
    planning_result: PlanningResult | None = None
    execution_result: ExecutionResult | None = None
    verification_result: VerificationResult | None = None

    def emit_event(self, event: JSONObject) -> None:
        """Push an SSE event onto the queue (non-blocking)."""
        if self.event_queue is not None:
            self.event_queue.put_nowait(event)

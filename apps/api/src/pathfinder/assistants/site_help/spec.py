"""Site help as one assistant: a single agent over the bare turn state.

It declares no phases, no sub-agents, no domain state and no identity
requirement. The application's own session auth still applies.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from assistant_core.graph.runtime import AssistantDeps, TurnContext
from assistant_core.graph.single_agent import single_agent_graph
from assistant_core.graph.turn_state import TurnState
from assistant_core.platform.db import async_session_factory
from assistant_core.spec import AssistantSpec, TurnContextRequest, TurnStart
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

from pathfinder.assistants.site_help.agent import build_site_help_agent
from pathfinder.assistants.site_help.mock import build_site_help_mock
from pathfinder.services.quota import accumulate

SITE_HELP_ASSISTANT_ID = "site_help"


def build_initial_state(start: TurnStart) -> TurnState:
    return TurnState(**start.state_kwargs())


async def build_turn_context(request: TurnContextRequest) -> TurnContext:
    """The runtime's own per-turn resources, and nothing else."""
    return TurnContext(
        site_id=request.site_id,
        user_id=request.user_id,
        db_session_factory=async_session_factory,
        cancel_event=request.cancel_event,
        memory_store=request.memory_store,
        phase_models=dict(request.phase_models),
        phase_reasoning=dict(request.phase_reasoning),
    )


def build_deps(state: TurnState, context: TurnContext) -> AssistantDeps:
    return AssistantDeps(
        site_id=context.site_id,
        user_id=context.user_id,
        conversation_id=state.conversation_id,
        db_session_factory=context.db_session_factory,
        memory_store=context.memory_store,
        cancel_event=context.cancel_event,
    )


async def charge_usage(user_id: UUID, tokens: int, cost_usd: Decimal) -> None:
    """Site-help turns count against the same monthly budget as any other."""
    if tokens == 0 and cost_usd == 0:
        return
    async with async_session_factory() as session:
        await accumulate(session, user_id=user_id, tokens=tokens, cost_usd=cost_usd)
        await session.commit()


def build_graph(
    checkpointer: BaseCheckpointSaver[Any],
) -> CompiledStateGraph[TurnState, TurnContext, TurnState, TurnState]:
    return single_agent_graph(
        checkpointer=checkpointer,
        state_type=TurnState,
        context_type=TurnContext,
        build_agent=build_site_help_agent,
        build_deps=build_deps,
        charge_usage=charge_usage,
    )


def build_site_help_spec() -> AssistantSpec:
    return AssistantSpec(
        assistant_id=SITE_HELP_ASSISTANT_ID,
        build_graph=build_graph,
        build_initial_state=build_initial_state,
        build_turn_context=build_turn_context,
        build_mock_model=build_site_help_mock,
    )


__all__ = [
    "SITE_HELP_ASSISTANT_ID",
    "build_deps",
    "build_graph",
    "build_initial_state",
    "build_site_help_spec",
    "build_turn_context",
    "charge_usage",
]

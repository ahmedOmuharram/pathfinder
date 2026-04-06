"""Phase runner — resolves models, manages agent registry, runs single phases.

Owns the mapping from phase names to pydantic-ai agents and usage limits.
"""

import asyncio
from dataclasses import dataclass

from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.usage import UsageLimits

from veupath_chatbot.ai.agents.discovery import DISCOVERY_USAGE_LIMITS, discovery_agent
from veupath_chatbot.ai.agents.execution import (
    EXECUTION_USAGE_LIMITS,
    execution_agent,
)
from veupath_chatbot.ai.agents.planning import PLANNING_USAGE_LIMITS, planning_agent
from veupath_chatbot.ai.agents.verification import (
    VERIFICATION_USAGE_LIMITS,
    verification_agent,
)
from veupath_chatbot.ai.models.mock import get_mock_model
from veupath_chatbot.ai.orchestration.deps import AgentDeps
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.chat.streaming.node_streaming import (
    TurnCounters,
    merge_usage,
    stream_call_tools,
    stream_model_request,
)

# ── Phase agent registry ──────────────────────────────────────────────────

PHASE_AGENTS: dict[str, Agent[AgentDeps, str]] = {
    "discovery": discovery_agent,
    "planning": planning_agent,
    "execution": execution_agent,
    "verification": verification_agent,
}

PHASE_LIMITS: dict[str, UsageLimits] = {
    "discovery": DISCOVERY_USAGE_LIMITS,
    "planning": PLANNING_USAGE_LIMITS,
    "execution": EXECUTION_USAGE_LIMITS,
    "verification": VERIFICATION_USAGE_LIMITS,
}


# ── Phase config ──────────────────────────────────────────────────────────


@dataclass
class PhaseConfig:
    """Bundle of arguments for a single phase run (avoids >6 positional args)."""

    phase: str
    prompt: str
    deps: AgentDeps
    queue: asyncio.Queue[JSONObject]
    message_id: str
    counters: TurnCounters
    model_id: str = ""
    message_history: list[ModelMessage] | None = None
    usage_limits: UsageLimits | None = None


# ── Model resolution ──────────────────────────────────────────────────────


def is_mock_model(model_id: str) -> bool:
    """Check if the model ID indicates mock/deterministic mode."""
    return model_id.startswith("mock/")


def resolve_model(model_id: str) -> str | FunctionModel:
    """Resolve a model ID to a pydantic-ai model instance.

    Mock IDs (``mock/*``) return the deterministic FunctionModel.
    All other IDs are passed through as model name strings — pydantic-ai
    resolves them via its provider registry (Anthropic, OpenAI, etc.).
    """
    if is_mock_model(model_id):
        return get_mock_model()
    return model_id


# ── Phase execution ───────────────────────────────────────────────────────


async def run_phase(config: PhaseConfig) -> list[ModelMessage]:
    """Run a single pipeline phase, streaming all events to the queue.

    Returns the new messages produced during this phase so callers can
    forward conversational context to subsequent phases.
    """
    agent = PHASE_AGENTS[config.phase]

    # Override the agent's model with the resolved model for this turn.
    resolved = resolve_model(config.model_id)
    with agent.override(model=resolved):
        return await _run_phase_inner(config, agent)


async def _run_phase_inner(
    config: PhaseConfig, agent: Agent[AgentDeps, str]
) -> list[ModelMessage]:
    """Inner implementation of run_phase (separated for mock override)."""
    async with agent.iter(
        config.prompt,
        deps=config.deps,
        message_history=config.message_history,
        usage_limits=config.usage_limits,
    ) as run:
        async for node in run:
            if Agent.is_model_request_node(node):
                await stream_model_request(
                    node, run, config.queue, config.message_id, config.counters
                )
            elif Agent.is_call_tools_node(node):
                await stream_call_tools(node, run, config.queue, config.deps)

        merge_usage(config.counters, run.usage())

        return run.new_messages()

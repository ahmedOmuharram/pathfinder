"""Phase runner — resolves models, manages agent registry, runs single phases.

Owns the mapping from phase names to pydantic-ai agents and usage limits.
"""

import asyncio
from dataclasses import dataclass

from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.usage import UsageLimits

from pathfinder.ai.agents.discovery import DISCOVERY_USAGE_LIMITS, discovery_agent
from pathfinder.ai.agents.execution import (
    EXECUTION_USAGE_LIMITS,
    execution_agent,
)
from pathfinder.ai.agents.planning import PLANNING_USAGE_LIMITS, planning_agent
from pathfinder.ai.agents.scoping import SCOPING_USAGE_LIMITS, scoping_agent
from pathfinder.ai.agents.verification import (
    VERIFICATION_USAGE_LIMITS,
    verification_agent,
)
from pathfinder.ai.models.mock import get_mock_model
from pathfinder.ai.models.settings import build_model_settings
from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.platform.types import JSONObject, ReasoningEffort
from pathfinder.services.chat.streaming.node_streaming import (
    StreamMessageContext,
    TurnCounters,
    merge_usage,
    stream_call_tools,
    stream_model_request,
)

# ── Phase agent registry ──────────────────────────────────────────────────

PHASE_AGENTS: dict[str, Agent[AgentDeps, str]] = {
    "scoping": scoping_agent,
    "discovery": discovery_agent,
    "planning": planning_agent,
    "execution": execution_agent,
    "verification": verification_agent,
}

PHASE_LIMITS: dict[str, UsageLimits] = {
    "scoping": SCOPING_USAGE_LIMITS,
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
    message_group_id: str | None = None
    model_id: str = ""
    reasoning_effort: ReasoningEffort = "medium"
    message_history: list[ModelMessage] | None = None
    usage_limits: UsageLimits | None = None

    @property
    def run_metadata(self) -> dict[str, str]:
        """Metadata for pydantic-ai agent runs — flows to OTEL spans."""
        return {
            "phase": self.phase,
            "site_id": self.deps.site_id,
            "user_id": str(self.deps.user_id or ""),
        }


# ── Model resolution ──────────────────────────────────────────────────────

# Cross-provider fallback chains. If the primary fails, try alternatives.
_FALLBACK_CHAINS: dict[str, list[str]] = {
    "anthropic": ["openai:gpt-5", "google:gemini-3.1-pro-preview"],
    "openai": ["anthropic:claude-sonnet-4-6", "google:gemini-3.1-pro-preview"],
    "google": ["anthropic:claude-sonnet-4-6", "openai:gpt-5"],
}


def is_mock_model(model_id: str) -> bool:
    """Check if the model ID indicates mock/deterministic mode."""
    return model_id.startswith("mock/")


def resolve_model(model_id: str) -> FallbackModel | FunctionModel:
    """Resolve a model ID to a pydantic-ai model instance.

    Mock IDs (``mock/*``) return the deterministic FunctionModel.
    All other IDs are wrapped in a FallbackModel with cross-provider
    fallbacks for production resilience.

    Normalizes catalog slash format (``openai/gpt-4.1``) to pydantic-ai
    colon format (``openai:gpt-4.1``).
    """
    if is_mock_model(model_id):
        return get_mock_model()

    normalized = model_id.replace("/", ":", 1)
    provider = normalized.split(":", 1)[0]
    fallbacks = _FALLBACK_CHAINS.get(provider, [])

    return FallbackModel(normalized, *fallbacks)


# ── Phase execution ───────────────────────────────────────────────────────


async def run_phase(config: PhaseConfig) -> list[ModelMessage]:
    """Run a single pipeline phase, streaming all events to the queue.

    Returns the new messages produced during this phase so callers can
    forward conversational context to subsequent phases.
    """
    agent = PHASE_AGENTS[config.phase]

    # Override the agent's model (and provider-specific settings) for this turn.
    resolved = resolve_model(config.model_id)
    settings = build_model_settings(config.model_id)
    with agent.override(model=resolved, model_settings=settings):
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
        metadata=config.run_metadata,
    ) as run:
        phase_exit_requested = False
        async for node in run:
            if Agent.is_model_request_node(node):
                await stream_model_request(
                    node,
                    run,
                    config.queue,
                    StreamMessageContext(
                        message_id=config.message_id,
                        message_group_id=config.message_group_id,
                        phase=config.phase,
                    ),
                    config.counters,
                )
            elif Agent.is_call_tools_node(node):
                phase_exit_requested = await stream_call_tools(
                    node,
                    run,
                    config.queue,
                    config.deps,
                    config.counters,
                )
                if phase_exit_requested:
                    break

        merge_usage(config.counters, run.usage())
        if phase_exit_requested:
            # We intentionally stop before pydantic-ai asks the model to
            # consume the finish_* tool result. That keeps phase exits
            # immediate, but it means run.new_messages() would contain
            # unresolved tool-call history that cannot be replayed into the
            # next phase as message_history.
            return []

        return run.new_messages()

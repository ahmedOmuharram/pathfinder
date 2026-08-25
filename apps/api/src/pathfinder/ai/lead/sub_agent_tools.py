"""Shared context for the Lead Agent's sub-agent dispatches.

The Lead's ``LeadDeps``, the per-phase model resolution and the budget the
dispatch runs under. The streaming engine lives in ``sub_agent_stream`` and
the tool wrappers in ``sub_agent_dispatch``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from assistant_core.capabilities.repetition_guard import ToolRepetitionGuard
from assistant_core.graph.turn_state import SubAgentApprovalPending
from assistant_core.memory.schemas import MemoryValue
from pydantic_ai.usage import RunUsage, UsageLimits

from pathfinder.ai.agents.execution import EXECUTION_MODEL, build_execution_agent
from pathfinder.ai.agents.frame import FRAME_MODEL, build_frame_agent
from pathfinder.ai.agents.roles import PhaseRole
from pathfinder.ai.agents.tool_vocabulary import build_tool_repetition_guard
from pathfinder.ai.agents.verification import (
    VERIFICATION_MODEL,
    build_verification_agent,
)
from pathfinder.ai.graph.runtime import AgentDeps, Context
from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.lead.intent import UserIntent
from pathfinder.ai.models.mock import get_mock_model
from pathfinder.ai.models.settings import build_model_settings
from pathfinder.ai.models.tiers import PhaseTierConfig, resolve_phase_tier_config
from pathfinder.platform.config import get_settings

# Binding one criterion costs about seven calls: find a search, read it, read a
# parameter or two, set the criterion. Reading the ledger and setting the
# structure are paid once for the pass.
CALLS_PER_CRITERION = 7
STRUCTURE_CALLS = 8
# A pass below the floor cannot recover from a single wrong search. The cap is
# what stops an overstated count from spending a whole turn.
MIN_PHASE_TOOL_CALLS = 40
MAX_PHASE_TOOL_CALLS = 160
_PHASE_TOKEN_LIMIT = 2_000_000


def phase_usage_limits(declared_criteria: int) -> UsageLimits:
    """The ceiling for one sub-agent pass over ``declared_criteria`` criteria."""
    wanted = declared_criteria * CALLS_PER_CRITERION + STRUCTURE_CALLS
    calls = max(MIN_PHASE_TOOL_CALLS, min(MAX_PHASE_TOOL_CALLS, wanted))
    return UsageLimits(
        request_limit=calls,
        tool_calls_limit=calls,
        total_tokens_limit=_PHASE_TOKEN_LIMIT,
    )


# A dispatch builds its own agent, so the map holds factories. The model each
# factory bakes in is a constant, because a default-model read runs after every
# inner tool call and must not construct an agent.
BUILD_SUB_AGENT_BY_ROLE: dict[PhaseRole, Callable[[], Any]] = {
    "frame": build_frame_agent,
    "execution": build_execution_agent,
    "verification": build_verification_agent,
}

SUB_AGENT_MODEL_BY_ROLE: dict[PhaseRole, str] = {
    "frame": FRAME_MODEL,
    "execution": EXECUTION_MODEL,
    "verification": VERIFICATION_MODEL,
}

TOOL_TO_PHASE_ROLE: dict[str, PhaseRole] = {
    "frame_problem": "frame",
    "recover_failed_steps": "execution",
    "verify_strategy": "verification",
}

PendingApprovalPhase = Literal["frame", "build", "verification", "lead"]

# The label the approval card carries for a sub-agent's own approval-required
# tool. It names the phase the user sees, not the role that runs it.
SUB_AGENT_APPROVAL_PHASE: dict[str, PendingApprovalPhase] = {
    "frame": "frame",
    "execution": "build",
    "verification": "verification",
}


def phase_default_model_id(role: PhaseRole) -> str:
    """The phase's model when the user pinned nothing: the configured
    ``(default_provider, default_tier)`` preset, else the model its factory
    bakes in."""
    cfg = _configured_tier_config(role)
    if cfg is not None:
        return cfg.model_id
    return SUB_AGENT_MODEL_BY_ROLE[role]


def _configured_tier_config(role: PhaseRole) -> PhaseTierConfig | None:
    settings = get_settings()
    return resolve_phase_tier_config(
        settings.default_provider, settings.default_tier, role
    )


def sub_agent_model_id(tool_name: str) -> str:
    """Model id for a sub-agent tool name. ``build_strategy`` is declarative
    (no LLM); everything else maps to the underlying phase agent's model.
    """
    if tool_name == "build_strategy":
        return "declarative:no-llm"
    role = TOOL_TO_PHASE_ROLE.get(tool_name)
    if role is None:
        return ""
    return phase_default_model_id(role)


def phase_override_kwargs(
    runtime: Context,
    role: PhaseRole,
) -> dict[str, Any]:
    """Resolve the model and the provider settings for a phase run.

    The model is the user pick, else the phase default. Settings always
    accompany it, because caching is provider specific.
    """
    if get_settings().pathfinder_chat_provider.strip().lower() == "mock":
        return {"model": get_mock_model()}
    effective_model = runtime.phase_models.get(role) or phase_default_model_id(role)
    tier_cfg = _configured_tier_config(role)
    effort = runtime.phase_reasoning.get(role) or (
        tier_cfg.reasoning_effort if tier_cfg is not None else None
    )
    return {
        "model": effective_model,
        "model_settings": build_model_settings(effective_model, thinking=effort),
    }


@dataclass
class SubAgentRunUsage:
    """Usage from one sub-agent dispatch.

    Each phase can run a different model, so the cost uses the sub-agent's
    own model pricing, not the Lead's.
    """

    usage: RunUsage
    model_name: str | None
    provider_name: str | None
    provider_url: str | None
    parent_tool_call_id: str


@dataclass
class LeadDeps:
    """The Lead Agent's runtime context.

    Mutates ``state`` in place as sub-agent tools run; the Lead's node
    turns the final ``state`` into a langgraph state delta at turn end.
    """

    state: PipelineState
    intent: UserIntent | None
    runtime: Context
    retrieved_memories: list[MemoryValue]
    record_sub_agent_usage: Callable[[SubAgentRunUsage], None] = field(
        default=lambda _u: None,
    )
    tool_repetition_guard: ToolRepetitionGuard = field(
        default_factory=build_tool_repetition_guard,
    )
    # Suspended sub-agent runs, keyed by the dispatch tool call that stopped at
    # an approval. The Lead's node checkpoints the run the answer re-enters.
    pending_sub_agent_approvals: dict[str, SubAgentApprovalPending] = field(
        default_factory=dict,
    )


def apply_agent_state(deps: LeadDeps, agent_deps: AgentDeps) -> None:
    deps.state.domain.discovered_searches = dict(
        agent_deps.agent_state.discovered_searches,
    )
    draft = agent_deps.agent_state.operational_spec_draft
    if draft.criteria or draft.dropped:
        deps.state.domain.operational_spec = draft

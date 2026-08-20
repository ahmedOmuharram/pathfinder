"""Shared context for the Lead Agent's sub-agent dispatches.

The Lead's ``LeadDeps``, the per-phase model resolution and the budget the
dispatch runs under. The streaming engine lives in ``sub_agent_stream`` and
the tool wrappers in ``sub_agent_dispatch``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic_ai.usage import RunUsage, UsageLimits

from pathfinder.ai.agents.execution import execution_agent
from pathfinder.ai.agents.frame import frame_agent
from pathfinder.ai.agents.roles import PhaseRole
from pathfinder.ai.agents.verification import verification_agent
from pathfinder.ai.graph.runtime import AgentDeps, Context
from pathfinder.ai.graph.state import PipelineState, SubAgentApprovalPending
from pathfinder.ai.lead.intent import UserIntent
from pathfinder.ai.memory.schemas import MemoryValue
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


SUB_AGENT_BY_ROLE: dict[PhaseRole, Any] = {
    "frame": frame_agent,
    "execution": execution_agent,
    "verification": verification_agent,
}

TOOL_TO_PHASE_ROLE: dict[str, PhaseRole] = {
    "frame_problem": "frame",
    "recover_failed_steps": "execution",
    "verify_strategy": "verification",
}


def _model_id_str(agent: Any) -> str:
    """The stable ``provider:model`` id baked into an agent at construction."""
    model = agent.model
    if model is None:
        return ""
    if isinstance(model, str):
        return model
    return str(model.model_id)


def phase_default_model_id(role: PhaseRole) -> str:
    """The phase's model when the user pinned nothing: the configured
    ``(default_provider, default_tier)`` preset, else the agent's baked model."""
    cfg = _configured_tier_config(role)
    if cfg is not None:
        return cfg.model_id
    return _model_id_str(SUB_AGENT_BY_ROLE[role])


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
    # Suspended sub-agent runs, keyed by the dispatch tool call that stopped at
    # an approval. The Lead's node checkpoints the run the answer re-enters.
    pending_sub_agent_approvals: dict[str, SubAgentApprovalPending] = field(
        default_factory=dict,
    )


def apply_agent_state(deps: LeadDeps, agent_deps: AgentDeps) -> None:
    deps.state.discovered_searches = dict(
        agent_deps.agent_state.discovered_searches,
    )
    draft = agent_deps.agent_state.operational_spec_draft
    if draft.criteria or draft.dropped:
        deps.state.operational_spec = draft

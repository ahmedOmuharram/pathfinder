"""Phase-role registry: maps the UI's per-phase model selectors to agents."""

from __future__ import annotations

from typing import Any

from pydantic_ai import Agent

from pathfinder.ai.agents.discovery import discovery_agent
from pathfinder.ai.agents.execution import execution_agent
from pathfinder.ai.agents.planning import planning_agent
from pathfinder.ai.agents.roles import PHASE_ROLES, PhaseRole
from pathfinder.ai.agents.scoping import scoping_agent
from pathfinder.ai.agents.verification import verification_agent
from pathfinder.ai.lead.lead_agent import lead_agent

PHASE_AGENTS: dict[PhaseRole, Agent[Any, Any]] = {
    "lead": lead_agent,
    "scoping": scoping_agent,
    "discovery": discovery_agent,
    "planning": planning_agent,
    "execution": execution_agent,
    "verification": verification_agent,
}


def phase_default_model_id(role: PhaseRole) -> str:
    """The compile-time model id baked into the phase's agent."""
    agent = PHASE_AGENTS[role]
    model = agent.model
    if model is None:
        return ""
    if isinstance(model, str):
        return model
    return str(model.model_id)


def phase_defaults() -> dict[PhaseRole, str]:
    return {role: phase_default_model_id(role) for role in PHASE_ROLES}


__all__ = [
    "PHASE_AGENTS",
    "PHASE_ROLES",
    "PhaseRole",
    "phase_default_model_id",
    "phase_defaults",
]

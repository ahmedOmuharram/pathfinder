"""Phase-role registry: the model each role runs on when the user pins nothing."""

from __future__ import annotations

from pathfinder.ai.agents.execution import execution_agent
from pathfinder.ai.agents.frame import frame_agent
from pathfinder.ai.agents.verification import verification_agent
from pathfinder.ai.lead.lead_agent import LEAD_MODEL
from pathfinder.ai.models.settings import baked_model_id

__all__ = ["phase_defaults"]


def phase_defaults() -> dict[str, str]:
    """The compile-time model of every role the product declares.

    The Lead is built per turn, so its default is the model its factory bakes
    in rather than a model read off a live agent.
    """
    return {
        "lead": LEAD_MODEL,
        "frame": baked_model_id(frame_agent),
        "execution": baked_model_id(execution_agent),
        "verification": baked_model_id(verification_agent),
    }

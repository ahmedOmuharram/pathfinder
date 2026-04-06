"""SSE event payload schemas for the plan system and pipeline phases.

These models define the typed payloads for plan-related SSE events
(plan presentation, plan updates, decision points) and pipeline phase
change events.  They live in ``platform`` so that services, AI
orchestration, and the event-sourcing layer can all use them without
importing from transport.
"""

from typing import Literal

from pydantic import Field

from veupath_chatbot.platform.pydantic_base import CamelModel
from veupath_chatbot.platform.types import JSONObject


class PhaseChangeEventData(CamelModel):
    """Payload for ``phase_change`` SSE events.

    Emitted by the state machine listener when the pipeline enters or
    exits a phase.
    """

    phase: Literal[
        "discovery", "planning", "execution", "verification", "completed"
    ]
    status: Literal["started", "completed", "failed", "awaiting_approval"]
    validation_error: str | None = Field(
        default=None,
        description="Validation gate error message if the phase failed validation.",
    )


class PlanPresentedEventData(CamelModel):
    """Payload for ``plan_presented`` SSE events."""

    plan: JSONObject


class PlanUpdatedEventData(CamelModel):
    """Payload for ``plan_updated`` SSE events."""

    plan_id: str
    updates: JSONObject


class DecisionPresentedEventData(CamelModel):
    """Payload for ``decision_presented`` SSE events."""

    decision_id: str
    question: str
    options: list[JSONObject]
    context: str
    recommendation: str | None = None


class PlanningThoughtEventData(CamelModel):
    """Payload for ``planning_thought`` SSE events.

    Emitted when the model uses ``<plan-thinking>`` tags in its response.
    The frontend renders these in a collapsible "Strategy Thinking" section.
    """

    thought: str

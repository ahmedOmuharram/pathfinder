"""Typed payloads for plan-related data-parts."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, JsonValue

from shared_py.pydantic_base import CamelModel


SlotStatus = Literal[
    "set",
    "default",
    "needs_discovery",
    "needs_user_input",
    "user_set",
]


class PlanSlotOption(CamelModel):
    """One option presented inside a NEEDS_USER_INPUT slot's question."""

    label: str
    value: JsonValue
    description: str = ""
    recommended: bool = False


class PlanSlotForm(CamelModel):
    """A NEEDS_USER_INPUT slot the submit_plan card must render as a form field.

    Carries everything the React component needs: the param's WDK type
    (so it picks the right widget), the question text, optional select
    options, and the step+param keys used when posting the answer back
    via ``data-plan-slot-answers``.
    """

    step_id: str
    param_name: str
    param_type: str
    status: SlotStatus
    required: bool = False
    question: str
    context: str = ""
    options: list[PlanSlotOption] = Field(default_factory=list)


class PlannedStep(CamelModel):
    order: int = Field(ge=0)
    search_name: str
    rationale: str | None = None
    parameters: dict[str, JsonValue] = Field(default_factory=dict)


class PlanArtifact(CamelModel):
    """A proposed plan (not yet applied)."""

    plan_id: str
    steps: list[PlannedStep]
    rationale: str
    slots: list[PlanSlotForm] = Field(default_factory=list)


class PlanUpdate(CamelModel):
    """Update to an existing plan."""

    plan_id: str
    status: Literal["proposed", "revised", "applied", "rejected"]
    reason: str | None = None

"""Typed payloads for plan-related data-parts."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, JsonValue

from shared_py.pydantic_base import CamelModel


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


class PlanUpdate(CamelModel):
    """Update to an existing plan."""

    plan_id: str
    status: Literal["proposed", "revised", "applied", "rejected"]
    reason: str | None = None


class DecisionPresented(CamelModel):
    """A branching decision for the user to resolve."""

    decision_type: str
    options: list[dict[str, JsonValue]]
    rationale: str | None = None

"""Typed output models for each phase agent (``output_type=<PhaseDecision>``).

When an agent produces one of these, pydantic-ai fires ``FinalResultEvent`` and
the pipeline dispatcher reads ``run.result.output`` to drive the state machine's
transition. These models replace the legacy ``finish_*`` exit tools — every
phase agent returns a typed ``PhaseDecision`` as its structured output instead
of calling a custom finish tool.

Each ``next_action`` literal is a valid state-machine transition label. Adding
a new branch means adding a case to both this module and ``AgentPipeline`` in
``pathfinder.ai.orchestration.pipeline``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ScopingDecision(BaseModel):
    """Structured exit from the scoping phase."""

    next_action: Literal[
        "advance_to_discovery",
        "advance_to_planning",
        "need_more_input",
    ]
    problem_frame: str
    discovered_searches: list[str] = Field(default_factory=list)
    reason: str


class DiscoveryDecision(BaseModel):
    """Structured exit from the discovery phase."""

    next_action: Literal[
        "advance_to_planning",
        "advance_to_execution",
        "need_more_input",
    ]
    discovered_searches: list[str]
    problem_frame_refined: str | None = None
    reason: str


class PlanningDecision(BaseModel):
    """Structured exit from the planning phase."""

    next_action: Literal["advance_to_execution", "request_revision", "abort"]
    plan_id: str
    reason: str


class ExecutionDecision(BaseModel):
    """Structured exit from the execution phase."""

    next_action: Literal["advance_to_verification", "retry", "abort"]
    executed_steps: list[str]
    reason: str


class VerificationDecision(BaseModel):
    """Structured exit from the verification phase."""

    next_action: Literal["complete", "retry_execution", "abort"]
    verification_notes: str
    reason: str

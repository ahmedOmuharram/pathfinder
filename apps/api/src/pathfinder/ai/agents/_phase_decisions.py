from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field


class ScopingDecision(BaseModel):
    phase: Literal["scoping"] = "scoping"
    next_action: Literal[
        "advance_to_discovery",
        "advance_to_planning",
        "need_more_input",
    ]


class DiscoveryDecision(BaseModel):
    phase: Literal["discovery"] = "discovery"
    next_action: Literal[
        "advance_to_planning",
        "advance_to_execution",
        "need_more_input",
    ]


class PlanningDecision(BaseModel):
    phase: Literal["planning"] = "planning"
    next_action: Literal["advance_to_execution", "request_revision", "abort"]


class ExecutionDecision(BaseModel):
    phase: Literal["execution"] = "execution"
    next_action: Literal["advance_to_verification", "retry", "abort"]


class VerificationDecision(BaseModel):
    phase: Literal["verification"] = "verification"
    next_action: Literal["complete", "retry_execution", "abort"]


PhaseDecision = Annotated[
    ScopingDecision
    | DiscoveryDecision
    | PlanningDecision
    | ExecutionDecision
    | VerificationDecision,
    Field(discriminator="phase"),
]

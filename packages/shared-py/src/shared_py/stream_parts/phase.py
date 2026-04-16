from __future__ import annotations

from typing import Literal

from pydantic import Field

from shared_py.pydantic_base import CamelModel

PhaseName = Literal[
    "scoping",
    "discovery",
    "planning",
    "execution",
    "verification",
    "completed",
]
PhaseStatus = Literal[
    "started", "completed", "failed", "awaiting_approval", "awaiting_input"
]


class PhaseChange(CamelModel):
    phase: PhaseName
    status: PhaseStatus
    duration_ms: int | None = Field(default=None, ge=0)
    reason: str | None = None

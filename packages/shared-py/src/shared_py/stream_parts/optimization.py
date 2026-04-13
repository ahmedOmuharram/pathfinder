"""Typed payload for optimization_progress data-part."""

from __future__ import annotations

from pydantic import Field

from shared_py.pydantic_base import CamelModel


class OptimizationSnapshot(CamelModel):
    trial_index: int = Field(ge=0)
    total_trials: int = Field(ge=1)
    best_score: float
    current_score: float
    is_pareto: bool

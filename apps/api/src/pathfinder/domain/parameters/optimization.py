from __future__ import annotations

from typing import Literal, Self

from assistant_core.platform.pydantic_base import CamelModel, RoundedFloat
from pydantic import ConfigDict, Field, model_validator

from pathfinder.domain.parameters.values import ParamValue


class VariantSpec(CamelModel):
    """One concrete parameter configuration in a sweep grid.

    Frozen — instances flow through the parallel fan-out path and must
    not mutate after construction. Each variant evaluates one WDK trial.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    params: dict[str, ParamValue] = Field(default_factory=dict)


VariantStatus = Literal["success", "failed"]


class VariantResult(CamelModel):
    """Outcome of a single variant evaluation in a parallel sweep.

    ``status="success"`` rows have ``score`` populated and metric fields
    filled when the WDK call returned data. ``status="failed"`` rows
    populate ``error`` with the exception message and leave metrics
    ``None``. The ``best`` selection in :class:`SweepResult` ranks
    successes by ``score``.
    """

    variant_id: str
    status: VariantStatus
    params: dict[str, ParamValue] = Field(default_factory=dict)
    score: RoundedFloat | None = None
    recall: RoundedFloat | None = None
    false_positive_rate: RoundedFloat | None = None
    estimated_size: int | None = None
    positive_hits: int | None = None
    negative_hits: int | None = None
    error: str | None = None


class SweepResult(CamelModel):
    """Top-level output of a parallel parameter sweep.

    ``variants`` preserves the input order from the Cartesian grid so the
    UI lane order matches the spec. ``best`` is the highest-scoring
    success or ``None`` if every variant failed.
    """

    variants: list[VariantResult]
    best: VariantResult | None

    @model_validator(mode="after")
    def _select_best(self) -> Self:
        """Compute ``best`` from the successful variants if not provided."""
        if self.best is not None:
            return self
        successes = [
            v for v in self.variants if v.status == "success" and v.score is not None
        ]
        if not successes:
            return self
        self.best = max(successes, key=lambda v: v.score or float("-inf"))
        return self

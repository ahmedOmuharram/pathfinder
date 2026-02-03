"""Strategy plan (DSL) request/response DTOs.

These models make the plan contract explicit in OpenAPI instead of using
`dict[str, Any]`, which is a major source of drift.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class PlanMetadata(BaseModel):
    name: str | None = None
    description: str | None = None
    siteId: str | None = None
    createdAt: str | None = None


class StepFilterSpec(BaseModel):
    name: str
    value: Any
    disabled: bool = False


class StepAnalysisSpec(BaseModel):
    analysisType: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    customName: str | None = None


class StepReportSpec(BaseModel):
    reportName: str = "standard"
    config: dict[str, Any] = Field(default_factory=dict)


class BasePlanNode(BaseModel):
    id: str | None = None
    displayName: str | None = None
    filters: list[StepFilterSpec] | None = None
    analyses: list[StepAnalysisSpec] | None = None
    reports: list[StepReportSpec] | None = None

    # Keep permissive for forward-compat with WDK payload quirks.
    model_config = {"extra": "allow"}


class ColocationParams(BaseModel):
    upstream: int = Field(ge=0)
    downstream: int = Field(ge=0)
    strand: str = "both"


class PlanNode(BasePlanNode):
    """
    Untyped recursive plan node (WDK-aligned).

    Kind is inferred from structure:
    - combine: primaryInput + secondaryInput
    - transform: primaryInput only
    - search: no inputs
    """

    searchName: str
    parameters: dict[str, Any] = Field(default_factory=dict)

    primaryInput: "PlanNode | None" = Field(default=None)
    secondaryInput: "PlanNode | None" = Field(default=None)

    # Required iff secondaryInput present
    operator: str | None = None
    colocationParams: ColocationParams | None = None

    model_config = {"extra": "allow"}

    @model_validator(mode="after")
    def _validate_structure(self) -> "PlanNode":
        # secondary requires primary
        if self.secondaryInput is not None and self.primaryInput is None:
            raise ValueError("secondaryInput requires primaryInput")

        # operator required when secondary present
        if self.secondaryInput is not None and not self.operator:
            raise ValueError("operator is required when secondaryInput is present")

        # colocationParams constraints
        if self.operator == "COLOCATE" and self.colocationParams is None:
            raise ValueError("colocationParams is required when operator is COLOCATE")
        if self.operator != "COLOCATE" and self.colocationParams is not None:
            raise ValueError("colocationParams is only allowed when operator is COLOCATE")

        return self


class StrategyPlan(BaseModel):
    recordType: str
    root: PlanNode
    metadata: PlanMetadata | None = None

    model_config = {"extra": "allow"}


class PlanNormalizeRequest(BaseModel):
    siteId: str
    plan: StrategyPlan


class PlanNormalizeResponse(BaseModel):
    plan: StrategyPlan
    warnings: list[dict[str, Any]] | None = None


# Resolve forward references for recursive node types.
PlanNode.model_rebuild()
StrategyPlan.model_rebuild()


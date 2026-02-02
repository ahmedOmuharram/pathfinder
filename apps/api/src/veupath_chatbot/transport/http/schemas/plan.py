"""Strategy plan (DSL) request/response DTOs.

These models make the plan contract explicit in OpenAPI instead of using
`dict[str, Any]`, which is a major source of drift.
"""

from __future__ import annotations

from typing import Any, Annotated, Literal

from pydantic import BaseModel, Field


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


class SearchPlanNode(BasePlanNode):
    type: Literal["search"]
    searchName: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class ColocationParams(BaseModel):
    upstream: int = Field(ge=0)
    downstream: int = Field(ge=0)
    strand: str = "both"


class CombinePlanNode(BasePlanNode):
    type: Literal["combine"]
    operator: str
    left: "PlanNode"
    right: "PlanNode"
    colocationParams: ColocationParams | None = None


class TransformPlanNode(BasePlanNode):
    type: Literal["transform"]
    transformName: str
    input: "PlanNode"
    parameters: dict[str, Any] | None = None


PlanNode = Annotated[
    SearchPlanNode | CombinePlanNode | TransformPlanNode, Field(discriminator="type")
]


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
SearchPlanNode.model_rebuild()
CombinePlanNode.model_rebuild()
TransformPlanNode.model_rebuild()
StrategyPlan.model_rebuild()


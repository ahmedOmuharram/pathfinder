"""Strategy plan (DSL) request/response DTOs.

These models make the plan contract explicit in OpenAPI instead of using
`dict[str, Any]`, which is a major source of drift.
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue


class PlanMetadata(BaseModel):
    name: str | None = None
    description: str | None = None
    siteId: str | None = None
    createdAt: str | None = None


class StepFilterSpec(BaseModel):
    name: str
    value: JSONValue
    disabled: bool = False


class StepAnalysisSpec(BaseModel):
    analysisType: str
    parameters: JSONObject = Field(default_factory=dict)
    customName: str | None = None


class StepReportSpec(BaseModel):
    reportName: str = "standard"
    config: JSONObject = Field(default_factory=dict)


class BasePlanNode(BaseModel):
    id: str | None = None
    displayName: str | None = None
    filters: list[StepFilterSpec] | None = None
    analyses: list[StepAnalysisSpec] | None = None
    reports: list[StepReportSpec] | None = None

    # Allow extra fields so the AI agent can store arbitrary WDK-originated
    # keys (e.g. ``wdkStepId``, ``estimatedSize``) without schema breakage.
    model_config = {"extra": "allow"}


class ColocationParams(BaseModel):
    upstream: int = Field(ge=0)
    downstream: int = Field(ge=0)
    strand: Literal["same", "opposite", "both"] = "both"


class PlanNode(BasePlanNode):
    """Untyped recursive plan node (WDK-aligned).

    Kind is inferred from structure:
    - combine: primaryInput + secondaryInput
    - transform: primaryInput only
    - search: no inputs


    """

    searchName: str
    parameters: JSONObject = Field(default_factory=dict)

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
            msg = "secondaryInput requires primaryInput"
            raise ValueError(msg)

        # operator required when secondary present
        if self.secondaryInput is not None and not self.operator:
            msg = "operator is required when secondaryInput is present"
            raise ValueError(msg)

        # colocationParams constraints
        if self.operator == "COLOCATE" and self.colocationParams is None:
            msg = "colocationParams is required when operator is COLOCATE"
            raise ValueError(msg)
        if self.operator != "COLOCATE" and self.colocationParams is not None:
            msg = "colocationParams is only allowed when operator is COLOCATE"
            raise ValueError(msg)

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
    warnings: JSONArray | None = None


# Resolve forward references for recursive node types.
PlanNode.model_rebuild()
StrategyPlan.model_rebuild()

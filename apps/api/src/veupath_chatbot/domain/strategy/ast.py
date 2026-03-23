"""AST node types for strategy representation (untyped tree)."""

from uuid import uuid4

from pydantic import Field, ValidationError, model_validator

from veupath_chatbot.domain.strategy.ops import ColocationParams, CombineOp
from veupath_chatbot.platform.pydantic_base import CamelModel
from veupath_chatbot.platform.types import JSONObject, JSONValue

# Sentinel search names for non-search nodes in the step graph.
COMBINE_SEARCH_NAME = "__combine__"
UNKNOWN_SEARCH_NAME = "__unknown__"


def generate_step_id() -> str:
    """Generate a unique step ID."""
    return f"step_{uuid4().hex[:8]}"


class StepFilter(CamelModel):
    """Filter applied to a step's result.

    WDK FilterValueArray element: { name: string, value: any, disabled?: boolean }.
    """

    name: str
    value: JSONValue = None
    disabled: bool = False

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: JSONValue) -> dict[str, JSONValue]:
        if not isinstance(data, dict):
            msg = "StepFilter requires a dict"
            raise TypeError(msg)
        name = data.get("name")
        if not isinstance(name, str) or not name:
            msg = "StepFilter requires a non-empty 'name'"
            raise ValueError(msg)
        return dict(data)

    @classmethod
    def from_list(cls, raw: object) -> list[StepFilter]:
        """Parse a tolerant list from raw JSON, silently dropping invalid items."""
        if not isinstance(raw, list):
            return []
        result: list[StepFilter] = []
        for item in raw:
            try:
                result.append(cls.model_validate(item))
            except (ValueError, TypeError, ValidationError):
                continue
        return result


class StepAnalysis(CamelModel):
    """Analysis configuration for a step.

    WDK fields: analysisType (str), parameters (JSONObject), customName (str|null).
    """

    analysis_type: str
    parameters: JSONObject = Field(default_factory=dict)
    custom_name: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: JSONValue) -> dict[str, JSONValue]:
        if not isinstance(data, dict):
            msg = "StepAnalysis requires a dict"
            raise TypeError(msg)
        result: dict[str, JSONValue] = dict(data)
        # Accept both camelCase alias and snake_case field name
        at = result.get("analysisType") or result.get("analysis_type")
        if not isinstance(at, str) or not at:
            msg = "StepAnalysis requires 'analysisType'"
            raise ValueError(msg)
        # Coerce non-dict parameters to empty dict
        if not isinstance(result.get("parameters"), dict):
            result["parameters"] = {}
        # Coerce non-string customName to None
        cn = result.get("customName") or result.get("custom_name")
        if cn is not None and not isinstance(cn, str):
            result.pop("customName", None)
            result.pop("custom_name", None)
        return result

    def to_dict(self) -> dict[str, JSONValue]:
        """Serialize; omits customName when empty."""
        d: dict[str, JSONValue] = super().to_dict()
        if not self.custom_name:
            d.pop("customName", None)
        return d

    @classmethod
    def from_list(cls, raw: object) -> list[StepAnalysis]:
        """Parse a tolerant list from raw JSON, silently dropping invalid items."""
        if not isinstance(raw, list):
            return []
        result: list[StepAnalysis] = []
        for item in raw:
            try:
                result.append(cls.model_validate(item))
            except (ValueError, TypeError, ValidationError):
                continue
        return result


class StepReport(CamelModel):
    """Report request attached to a step.

    WDK fields: reportName (str, default "standard"), config (JSONObject).
    """

    report_name: str = "standard"
    config: JSONObject = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: JSONValue) -> dict[str, JSONValue]:
        if not isinstance(data, dict):
            msg = "StepReport requires a dict"
            raise TypeError(msg)
        result: dict[str, JSONValue] = dict(data)
        # Coerce non-dict config to empty dict
        if not isinstance(result.get("config"), dict):
            result["config"] = {}
        return result

    @classmethod
    def from_list(cls, raw: object) -> list[StepReport]:
        """Parse a tolerant list from raw JSON, silently dropping invalid items."""
        if not isinstance(raw, list):
            return []
        result: list[StepReport] = []
        for item in raw:
            try:
                result.append(cls.model_validate(item))
            except (ValueError, TypeError, ValidationError):
                continue
        return result


class PlanStepNode(CamelModel):
    """Untyped recursive strategy node.

    Kind is inferred from structure:
    - combine: primary_input and secondary_input
    - transform: primary_input only
    - search: no inputs


    """

    search_name: str
    parameters: JSONObject = Field(default_factory=dict)
    primary_input: PlanStepNode | None = None
    secondary_input: PlanStepNode | None = None
    operator: CombineOp | None = None
    colocation_params: ColocationParams | None = None
    display_name: str | None = None
    filters: list[StepFilter] = Field(default_factory=list)
    analyses: list[StepAnalysis] = Field(default_factory=list)
    reports: list[StepReport] = Field(default_factory=list)
    wdk_weight: int | None = None
    id: str = Field(default_factory=generate_step_id)

    @model_validator(mode="after")
    def _validate_structure(self) -> PlanStepNode:
        if self.secondary_input is not None and self.primary_input is None:
            msg = "secondaryInput requires primaryInput"
            raise ValueError(msg)
        if self.secondary_input is not None and not self.operator:
            msg = "operator is required when secondaryInput is present"
            raise ValueError(msg)
        if self.operator == CombineOp.COLOCATE and self.colocation_params is None:
            msg = "colocationParams is required when operator is COLOCATE"
            raise ValueError(msg)
        if self.operator != CombineOp.COLOCATE and self.colocation_params is not None:
            msg = "colocationParams is only allowed when operator is COLOCATE"
            raise ValueError(msg)
        return self

    def infer_kind(self) -> str:
        if self.primary_input is not None and self.secondary_input is not None:
            return "combine"
        if self.primary_input is not None:
            return "transform"
        return "search"

    def to_dict(self) -> JSONObject:
        result: JSONObject = {
            "id": self.id,
            "searchName": self.search_name,
            "displayName": self.display_name or self.search_name,
            "parameters": self.parameters or {},
        }

        if self.primary_input is not None:
            result["primaryInput"] = self.primary_input.to_dict()
        if self.secondary_input is not None:
            result["secondaryInput"] = self.secondary_input.to_dict()
        if self.operator is not None:
            result["operator"] = self.operator.value
        if self.colocation_params is not None:
            result["colocationParams"] = self.colocation_params.to_dict()
        if self.filters:
            result["filters"] = [f.to_dict() for f in self.filters]
        if self.analyses:
            result["analyses"] = [a.to_dict() for a in self.analyses]
        if self.reports:
            result["reports"] = [r.to_dict() for r in self.reports]
        if self.wdk_weight is not None:
            result["wdkWeight"] = self.wdk_weight
        return result


class StrategyAST(CamelModel):
    """Complete strategy represented as an AST."""

    record_type: str
    root: PlanStepNode
    name: str | None = None
    description: str | None = None
    metadata: JSONObject | None = None

    def to_dict(self) -> JSONObject:
        """Convert to dictionary representation."""
        result: JSONObject = {
            "recordType": self.record_type,
            "root": self.root.to_dict(),
        }
        if self.name is not None:
            result["name"] = self.name
        if self.description is not None:
            result["description"] = self.description
        if self.metadata:
            result["metadata"] = self.metadata
        return result

    def get_all_steps(self) -> list[PlanStepNode]:
        """Get all steps in the tree (depth-first)."""
        steps: list[PlanStepNode] = []

        def visit(node: PlanStepNode) -> None:
            if node.primary_input is not None:
                visit(node.primary_input)
            if node.secondary_input is not None:
                visit(node.secondary_input)
            steps.append(node)

        visit(self.root)
        return steps

    def get_step_by_id(self, step_id: str) -> PlanStepNode | None:
        """Find a step by its ID.

        :param step_id: Step identifier.

        """
        for step in self.get_all_steps():
            if step.id == step_id:
                return step
        return None



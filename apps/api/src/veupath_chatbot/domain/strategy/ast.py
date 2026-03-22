"""AST node types for strategy representation (untyped tree)."""

from uuid import uuid4

from pydantic import Field, ValidationError, model_validator

from veupath_chatbot.domain.strategy.ops import ColocationParams, CombineOp
from veupath_chatbot.platform.pydantic_base import CamelModel
from veupath_chatbot.platform.types import JSONObject, JSONValue

# Sentinel search names for non-search nodes in the step graph.
COMBINE_SEARCH_NAME = "__combine__"
UNKNOWN_SEARCH_NAME = "__unknown__"


class StepTreeNode(CamelModel):
    """Node in a WDK step tree.

    Represents a single step with optional primary (and for combines, secondary)
    input references. Used to build the ``stepTree`` payload for WDK strategy
    creation. Pure data structure with no I/O.
    """

    step_id: int
    primary_input: StepTreeNode | None = None
    secondary_input: StepTreeNode | None = None


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
        metadata: JSONObject = dict(self.metadata or {})
        # Ensure name/description are always reflected in metadata.
        if self.name is not None:
            metadata["name"] = self.name
        if self.description is not None:
            metadata["description"] = self.description
        return {
            "recordType": self.record_type,
            "root": self.root.to_dict(),
            "metadata": metadata or None,
        }

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


def from_dict(data: JSONObject) -> StrategyAST:
    """Parse strategy from dictionary representation.

    :param data: Data dict.

    """

    def parse_node(node_data: JSONObject) -> PlanStepNode:
        search_name = node_data.get("searchName")
        if not isinstance(search_name, str) or not search_name:
            msg = "Missing searchName"
            raise ValueError(msg)

        params = node_data.get("parameters") or {}
        if not isinstance(params, dict):
            msg = "parameters must be an object"
            raise TypeError(msg)

        primary_raw = node_data.get("primaryInput")
        secondary_raw = node_data.get("secondaryInput")
        primary = parse_node(primary_raw) if isinstance(primary_raw, dict) else None
        secondary = (
            parse_node(secondary_raw) if isinstance(secondary_raw, dict) else None
        )

        op_raw = node_data.get("operator")
        operator = CombineOp(op_raw) if isinstance(op_raw, str) and op_raw else None

        colocation = ColocationParams.from_json(node_data.get("colocationParams"))

        # basic structural constraints
        if secondary is not None and primary is None:
            msg = "secondaryInput requires primaryInput"
            raise ValueError(msg)
        if secondary is not None and operator is None:
            msg = "operator is required when secondaryInput is present"
            raise ValueError(msg)
        if operator == CombineOp.COLOCATE and colocation is None:
            msg = "colocationParams is required when operator is COLOCATE"
            raise ValueError(msg)
        if operator != CombineOp.COLOCATE and colocation is not None:
            msg = "colocationParams is only allowed when operator is COLOCATE"
            raise ValueError(msg)

        display_name_raw = node_data.get("displayName")
        display_name = display_name_raw if isinstance(display_name_raw, str) else None
        id_raw = node_data.get("id")
        step_id = id_raw if isinstance(id_raw, str) else generate_step_id()
        wdk_weight_raw = node_data.get("wdkWeight")
        wdk_weight = (
            int(wdk_weight_raw) if isinstance(wdk_weight_raw, (int, float)) else None
        )
        return PlanStepNode(
            search_name=search_name,
            parameters=params,
            primary_input=primary,
            secondary_input=secondary,
            operator=operator,
            colocation_params=colocation,
            display_name=display_name,
            filters=StepFilter.from_list(node_data.get("filters")),
            analyses=StepAnalysis.from_list(node_data.get("analyses")),
            reports=StepReport.from_list(node_data.get("reports")),
            wdk_weight=wdk_weight,
            id=step_id,
        )

    record_type_raw = data.get("recordType")
    if not isinstance(record_type_raw, str):
        msg = "Missing or invalid recordType"
        raise TypeError(msg)

    root_raw = data.get("root")
    if not isinstance(root_raw, dict):
        msg = "Missing or invalid root"
        raise TypeError(msg)

    metadata_raw = data.get("metadata", {})
    metadata_obj = metadata_raw if isinstance(metadata_raw, dict) else {}

    name_raw = metadata_obj.get("name")
    name = name_raw if isinstance(name_raw, str) else None

    description_raw = metadata_obj.get("description")
    description = description_raw if isinstance(description_raw, str) else None

    return StrategyAST(
        record_type=record_type_raw,
        root=parse_node(root_raw),
        name=name,
        description=description,
        metadata=metadata_obj or None,
    )

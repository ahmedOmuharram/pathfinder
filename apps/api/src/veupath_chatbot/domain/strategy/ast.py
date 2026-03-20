"""AST node types for strategy representation (WDK-aligned, untyped tree)."""

from dataclasses import dataclass, field
from typing import Literal, cast
from uuid import uuid4

from veupath_chatbot.domain.strategy.ops import ColocationParams, CombineOp
from veupath_chatbot.platform.types import JSONObject, JSONValue

# Sentinel search names for non-search nodes in the step graph.
COMBINE_SEARCH_NAME = "__combine__"
UNKNOWN_SEARCH_NAME = "__unknown__"


class StepTreeNode:
    """Node in a WDK step tree.

    Represents a single step with optional primary (and for combines, secondary)
    input references. Used to build the ``stepTree`` payload for WDK strategy
    creation. Pure data structure with no I/O.
    """

    def __init__(
        self,
        step_id: int,
        primary_input: StepTreeNode | None = None,
        secondary_input: StepTreeNode | None = None,
    ) -> None:
        self.step_id = step_id
        self.primary_input = primary_input
        self.secondary_input = secondary_input

    def to_dict(self) -> JSONObject:
        """Convert to WDK stepTree format."""
        result: JSONObject = {"stepId": self.step_id}
        if self.primary_input:
            result["primaryInput"] = self.primary_input.to_dict()
        if self.secondary_input:
            result["secondaryInput"] = self.secondary_input.to_dict()
        return result


def generate_step_id() -> str:
    """Generate a unique step ID."""
    return f"step_{uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# Shared parsers for filters, analyses, reports, and colocation params.
# Used by both from_dict() and session.hydrate_graph_from_steps_data().
# ---------------------------------------------------------------------------


def parse_filters(raw: JSONValue) -> list[StepFilter]:
    """Parse a list of step filters from raw JSON data."""
    items = raw if isinstance(raw, list) else []
    filters: list[StepFilter] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str) or not name:
            continue
        filters.append(
            StepFilter(
                name=name,
                value=item.get("value"),
                disabled=bool(item.get("disabled", False)),
            )
        )
    return filters


def parse_analyses(raw: JSONValue) -> list[StepAnalysis]:
    """Parse a list of step analyses from raw JSON data."""
    items = raw if isinstance(raw, list) else []
    analyses: list[StepAnalysis] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        analysis_type = item.get("analysisType") or item.get("analysis_type")
        if not isinstance(analysis_type, str) or not analysis_type:
            continue
        params_raw = item.get("parameters")
        params: JSONObject = params_raw if isinstance(params_raw, dict) else {}
        custom_name_raw = item.get("customName") or item.get("custom_name")
        custom_name = custom_name_raw if isinstance(custom_name_raw, str) else None
        analyses.append(
            StepAnalysis(
                analysis_type=analysis_type,
                parameters=params,
                custom_name=custom_name,
            )
        )
    return analyses


def parse_reports(raw: JSONValue) -> list[StepReport]:
    """Parse a list of step reports from raw JSON data."""
    items = raw if isinstance(raw, list) else []
    reports: list[StepReport] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        report_name_raw = item.get("reportName") or item.get("report_name")
        report_name = (
            report_name_raw if isinstance(report_name_raw, str) else "standard"
        )
        config_raw = item.get("config")
        config: JSONObject = config_raw if isinstance(config_raw, dict) else {}
        reports.append(
            StepReport(
                report_name=report_name,
                config=config,
            )
        )
    return reports


def parse_colocation_params(raw: JSONValue) -> ColocationParams | None:
    """Parse colocation parameters from raw JSON data."""
    if not isinstance(raw, dict):
        return None
    upstream_raw = raw.get("upstream", 0)
    downstream_raw = raw.get("downstream", 0)
    strand_raw = raw.get("strand", "both")
    upstream = int(upstream_raw) if isinstance(upstream_raw, (int, float)) else 0
    downstream = int(downstream_raw) if isinstance(downstream_raw, (int, float)) else 0
    strand: Literal["same", "opposite", "both"]
    if isinstance(strand_raw, str) and strand_raw in ("same", "opposite", "both"):
        strand = cast("Literal['same', 'opposite', 'both']", strand_raw)
    else:
        strand = "both"
    return ColocationParams(upstream=upstream, downstream=downstream, strand=strand)


@dataclass
class StepFilter:
    """Filter applied to a step's result."""

    name: str
    value: JSONValue
    disabled: bool = False

    def to_dict(self) -> JSONObject:
        return {
            "name": self.name,
            "value": self.value,
            "disabled": self.disabled,
        }


@dataclass
class StepAnalysis:
    """Analysis configuration for a step."""

    analysis_type: str
    parameters: JSONObject = field(default_factory=dict)
    custom_name: str | None = None

    def to_dict(self) -> JSONObject:
        result: JSONObject = {
            "analysisType": self.analysis_type,
            "parameters": self.parameters,
        }
        if self.custom_name:
            result["customName"] = self.custom_name
        return result


@dataclass
class StepReport:
    """Report request attached to a step."""

    report_name: str = "standard"
    config: JSONObject = field(default_factory=dict)

    def to_dict(self) -> JSONObject:
        return {
            "reportName": self.report_name,
            "config": self.config,
        }


@dataclass
class PlanStepNode:
    """Untyped recursive strategy node.

    Kind is inferred from structure:
    - combine: primary_input and secondary_input
    - transform: primary_input only
    - search: no inputs


    """

    search_name: str
    parameters: JSONObject = field(default_factory=dict)
    primary_input: PlanStepNode | None = None
    secondary_input: PlanStepNode | None = None
    operator: CombineOp | None = None
    colocation_params: ColocationParams | None = None
    display_name: str | None = None
    filters: list[StepFilter] = field(default_factory=list)
    analyses: list[StepAnalysis] = field(default_factory=list)
    reports: list[StepReport] = field(default_factory=list)
    wdk_weight: int | None = None
    id: str = field(default_factory=generate_step_id)

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
            result["colocationParams"] = {
                "upstream": self.colocation_params.upstream,
                "downstream": self.colocation_params.downstream,
                "strand": self.colocation_params.strand,
            }
        if self.filters:
            result["filters"] = [f.to_dict() for f in self.filters]
        if self.analyses:
            result["analyses"] = [a.to_dict() for a in self.analyses]
        if self.reports:
            result["reports"] = [r.to_dict() for r in self.reports]
        if self.wdk_weight is not None:
            result["wdkWeight"] = self.wdk_weight
        return result


@dataclass
class StrategyAST:
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

        colocation = parse_colocation_params(node_data.get("colocationParams"))

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
            filters=parse_filters(node_data.get("filters")),
            analyses=parse_analyses(node_data.get("analyses")),
            reports=parse_reports(node_data.get("reports")),
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

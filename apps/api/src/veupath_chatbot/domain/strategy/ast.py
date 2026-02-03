"""AST node types for strategy representation (WDK-aligned, untyped tree)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from veupath_chatbot.domain.strategy.ops import CombineOp, ColocationParams


def generate_step_id() -> str:
    """Generate a unique step ID."""
    return f"step_{uuid4().hex[:8]}"


@dataclass
class StepFilter:
    """Filter applied to a step's result."""

    name: str
    value: Any
    disabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "disabled": self.disabled,
        }


@dataclass
class StepAnalysis:
    """Analysis configuration for a step."""

    analysis_type: str
    parameters: dict[str, Any] = field(default_factory=dict)
    custom_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = {
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
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "reportName": self.report_name,
            "config": self.config,
        }


@dataclass
class PlanStepNode:
    """
    Untyped recursive strategy node.

    Kind is inferred from structure:
    - combine: primary_input and secondary_input
    - transform: primary_input only
    - search: no inputs
    """

    search_name: str
    parameters: dict[str, Any] = field(default_factory=dict)
    primary_input: "PlanStepNode | None" = None
    secondary_input: "PlanStepNode | None" = None
    operator: CombineOp | None = None
    colocation_params: ColocationParams | None = None
    display_name: str | None = None
    filters: list[StepFilter] = field(default_factory=list)
    analyses: list[StepAnalysis] = field(default_factory=list)
    reports: list[StepReport] = field(default_factory=list)
    id: str = field(default_factory=generate_step_id)

    def infer_kind(self) -> str:
        if self.primary_input is not None and self.secondary_input is not None:
            return "combine"
        if self.primary_input is not None:
            return "transform"
        return "search"

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
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
        return result


@dataclass
class StrategyAST:
    """Complete strategy represented as an AST."""

    record_type: str
    root: PlanStepNode
    name: str | None = None
    description: str | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        metadata: dict[str, Any] = dict(self.metadata or {})
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
        """Find a step by its ID."""
        for step in self.get_all_steps():
            if step.id == step_id:
                return step
        return None


def from_dict(data: dict[str, Any]) -> StrategyAST:
    """Parse strategy from dictionary representation."""

    def parse_filters(node_data: dict[str, Any]) -> list[StepFilter]:
        filters = []
        for item in node_data.get("filters", []) or []:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not name:
                continue
            filters.append(
                StepFilter(
                    name=str(name),
                    value=item.get("value"),
                    disabled=bool(item.get("disabled", False)),
                )
            )
        return filters

    def parse_analyses(node_data: dict[str, Any]) -> list[StepAnalysis]:
        analyses = []
        for item in node_data.get("analyses", []) or []:
            if not isinstance(item, dict):
                continue
            analysis_type = item.get("analysisType") or item.get("analysis_type")
            if not analysis_type:
                continue
            analyses.append(
                StepAnalysis(
                    analysis_type=str(analysis_type),
                    parameters=item.get("parameters") or {},
                    custom_name=item.get("customName") or item.get("custom_name"),
                )
            )
        return analyses

    def parse_reports(node_data: dict[str, Any]) -> list[StepReport]:
        reports = []
        for item in node_data.get("reports", []) or []:
            if not isinstance(item, dict):
                continue
            report_name = item.get("reportName") or item.get("report_name") or "standard"
            reports.append(
                StepReport(
                    report_name=str(report_name),
                    config=item.get("config") or {},
                )
            )
        return reports

    def parse_node(node_data: dict[str, Any]) -> PlanStepNode:
        search_name = node_data.get("searchName")
        if not isinstance(search_name, str) or not search_name:
            raise ValueError("Missing searchName")

        params = node_data.get("parameters") or {}
        if not isinstance(params, dict):
            raise ValueError("parameters must be an object")

        primary_raw = node_data.get("primaryInput")
        secondary_raw = node_data.get("secondaryInput")
        primary = parse_node(primary_raw) if isinstance(primary_raw, dict) else None
        secondary = parse_node(secondary_raw) if isinstance(secondary_raw, dict) else None

        op_raw = node_data.get("operator")
        operator = CombineOp(op_raw) if isinstance(op_raw, str) and op_raw else None

        colocation = None
        if isinstance(node_data.get("colocationParams"), dict):
            cp = node_data["colocationParams"]
            colocation = ColocationParams(
                upstream=cp.get("upstream", 0),
                downstream=cp.get("downstream", 0),
                strand=cp.get("strand", "both"),
            )

        # basic structural constraints
        if secondary is not None and primary is None:
            raise ValueError("secondaryInput requires primaryInput")
        if secondary is not None and operator is None:
            raise ValueError("operator is required when secondaryInput is present")
        if operator == CombineOp.COLOCATE and colocation is None:
            raise ValueError("colocationParams is required when operator is COLOCATE")
        if operator != CombineOp.COLOCATE and colocation is not None:
            raise ValueError("colocationParams is only allowed when operator is COLOCATE")

        return PlanStepNode(
            search_name=search_name,
            parameters=params,
            primary_input=primary,
            secondary_input=secondary,
            operator=operator,
            colocation_params=colocation,
            display_name=node_data.get("displayName"),
            filters=parse_filters(node_data),
            analyses=parse_analyses(node_data),
            reports=parse_reports(node_data),
            id=node_data.get("id", generate_step_id()),
        )

    metadata = data.get("metadata", {})
    return StrategyAST(
        record_type=data["recordType"],
        root=parse_node(data["root"]),
        name=metadata.get("name") if isinstance(metadata, dict) else None,
        description=metadata.get("description") if isinstance(metadata, dict) else None,
        metadata=metadata if isinstance(metadata, dict) else None,
    )


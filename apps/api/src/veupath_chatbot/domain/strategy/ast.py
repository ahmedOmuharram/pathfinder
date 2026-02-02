"""AST node types for strategy representation."""

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
class SearchStep:
    """A search step that queries a VEuPathDB search question."""

    record_type: str
    search_name: str
    parameters: dict[str, Any]
    display_name: str | None = None
    filters: list[StepFilter] = field(default_factory=list)
    analyses: list[StepAnalysis] = field(default_factory=list)
    reports: list[StepReport] = field(default_factory=list)
    id: str = field(default_factory=generate_step_id)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        result = {
            "type": "search",
            "id": self.id,
            "searchName": self.search_name,
            "displayName": self.display_name or self.search_name,
            "parameters": self.parameters,
        }
        if self.filters:
            result["filters"] = [f.to_dict() for f in self.filters]
        if self.analyses:
            result["analyses"] = [a.to_dict() for a in self.analyses]
        if self.reports:
            result["reports"] = [r.to_dict() for r in self.reports]
        return result


@dataclass
class CombineStep:
    """A combine step that applies a set operation to two inputs."""

    op: CombineOp
    left: StepNode
    right: StepNode
    display_name: str | None = None
    filters: list[StepFilter] = field(default_factory=list)
    analyses: list[StepAnalysis] = field(default_factory=list)
    reports: list[StepReport] = field(default_factory=list)
    colocation_params: ColocationParams | None = None
    id: str = field(default_factory=generate_step_id)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        result: dict[str, Any] = {
            "type": "combine",
            "id": self.id,
            "displayName": self.display_name or f"{self.op.value}",
            "operator": self.op.value,
            "left": self.left.to_dict(),
            "right": self.right.to_dict(),
        }
        if self.colocation_params:
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
class TransformStep:
    """A transform step that modifies its input (e.g., orthology expansion)."""

    transform_name: str
    input: StepNode
    parameters: dict[str, Any] = field(default_factory=dict)
    display_name: str | None = None
    filters: list[StepFilter] = field(default_factory=list)
    analyses: list[StepAnalysis] = field(default_factory=list)
    reports: list[StepReport] = field(default_factory=list)
    id: str = field(default_factory=generate_step_id)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        result = {
            "type": "transform",
            "id": self.id,
            "displayName": self.display_name or self.transform_name,
            "transformName": self.transform_name,
            "input": self.input.to_dict(),
            "parameters": self.parameters,
        }
        if self.filters:
            result["filters"] = [f.to_dict() for f in self.filters]
        if self.analyses:
            result["analyses"] = [a.to_dict() for a in self.analyses]
        if self.reports:
            result["reports"] = [r.to_dict() for r in self.reports]
        return result


# Union type for all step nodes
StepNode = SearchStep | CombineStep | TransformStep


@dataclass
class StrategyAST:
    """Complete strategy represented as an AST."""

    record_type: str
    root: StepNode
    name: str | None = None
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "recordType": self.record_type,
            "root": self.root.to_dict(),
            "metadata": {
                "name": self.name,
                "description": self.description,
            },
        }

    def get_all_steps(self) -> list[StepNode]:
        """Get all steps in the tree (depth-first)."""
        steps: list[StepNode] = []

        def visit(node: StepNode) -> None:
            if isinstance(node, SearchStep):
                steps.append(node)
            elif isinstance(node, CombineStep):
                visit(node.left)
                visit(node.right)
                steps.append(node)
            elif isinstance(node, TransformStep):
                visit(node.input)
                steps.append(node)

        visit(self.root)
        return steps

    def get_step_by_id(self, step_id: str) -> StepNode | None:
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

    def parse_node(node_data: dict[str, Any]) -> StepNode:
        node_type = node_data.get("type")

        if node_type == "search":
            return SearchStep(
                record_type=data.get("recordType", ""),
                search_name=node_data["searchName"],
                parameters=node_data.get("parameters", {}),
                display_name=node_data.get("displayName"),
                filters=parse_filters(node_data),
                analyses=parse_analyses(node_data),
                reports=parse_reports(node_data),
                id=node_data.get("id", generate_step_id()),
            )
        if node_type == "combine":
            colocation = None
            if "colocationParams" in node_data:
                cp = node_data["colocationParams"]
                colocation = ColocationParams(
                    upstream=cp.get("upstream", 0),
                    downstream=cp.get("downstream", 0),
                    strand=cp.get("strand", "both"),
                )
            return CombineStep(
                op=CombineOp(node_data["operator"]),
                left=parse_node(node_data["left"]),
                right=parse_node(node_data["right"]),
                display_name=node_data.get("displayName"),
                colocation_params=colocation,
                filters=parse_filters(node_data),
                analyses=parse_analyses(node_data),
                reports=parse_reports(node_data),
                id=node_data.get("id", generate_step_id()),
            )
        if node_type == "transform":
            return TransformStep(
                transform_name=node_data["transformName"],
                input=parse_node(node_data["input"]),
                parameters=node_data.get("parameters", {}),
                display_name=node_data.get("displayName"),
                filters=parse_filters(node_data),
                analyses=parse_analyses(node_data),
                reports=parse_reports(node_data),
                id=node_data.get("id", generate_step_id()),
            )

        raise ValueError(f"Unknown node type: {node_type}")

    metadata = data.get("metadata", {})
    return StrategyAST(
        record_type=data["recordType"],
        root=parse_node(data["root"]),
        name=metadata.get("name"),
        description=metadata.get("description"),
    )


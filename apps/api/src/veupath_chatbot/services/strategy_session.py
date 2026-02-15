"""Stateful strategy session types (in-memory).

These types model the *working* state while a user (or an AI agent) is building a
VEuPathDB strategy during a chat session.

They are intentionally **not** part of the pure domain layer:
- They hold mutable state (steps/history/current draft strategy)
- They represent an application/session concept (chat + graph = strategy session)
"""

from __future__ import annotations

from uuid import uuid4

from veupath_chatbot.domain.strategy.ast import (
    PlanStepNode,
    StepAnalysis,
    StepFilter,
    StepReport,
    StrategyAST,
    from_dict,
)
from veupath_chatbot.domain.strategy.ops import ColocationParams, CombineOp
from veupath_chatbot.platform.types import (
    JSONArray,
    JSONObject,
    JSONValue,
    as_json_object,
)

Step = PlanStepNode


class StrategyGraph:
    """State for a single strategy graph."""

    def __init__(self, graph_id: str, name: str, site_id: str) -> None:
        self.id = graph_id
        self.name = name
        self.site_id = site_id
        # Best-effort record type context for the working graph (e.g. "gene").
        # Set when the first step is created or when importing a WDK strategy.
        self.record_type: str | None = None
        self.current_strategy: StrategyAST | None = None
        self.steps: dict[str, Step] = {}
        # Current subtree root IDs.  Every step creation updates this set:
        # the new step is added as a root and any inputs it consumes are
        # removed.  A complete strategy has exactly one root.
        self.roots: set[str] = set()
        self.history: list[JSONObject] = []
        self.last_step_id: str | None = None
        # Populated after build_strategy / compile — maps local step IDs to WDK IDs.
        self.wdk_step_ids: dict[str, int] = {}
        # Populated after build_strategy — maps local step IDs to estimatedSize.
        self.step_counts: dict[str, int | None] = {}
        # WDK strategy ID, set after build_strategy creates the strategy on WDK.
        self.wdk_strategy_id: int | None = None

    def add_step(self, step: Step) -> str:
        """Add a step and maintain the subtree-root set.

        The new step becomes a root.  If it consumes existing roots as
        ``primary_input`` or ``secondary_input``, those are removed from the
        root set (they are now internal nodes of the new step's subtree).
        """
        self.steps[step.id] = step
        # The new step is always a root of its subtree.
        self.roots.add(step.id)
        # Inputs consumed by this step are no longer roots.
        if step.primary_input and step.primary_input.id in self.roots:
            self.roots.discard(step.primary_input.id)
        if step.secondary_input and step.secondary_input.id in self.roots:
            self.roots.discard(step.secondary_input.id)
        self.last_step_id = step.id
        return step.id

    def get_step(self, step_id: str) -> Step | None:
        """Get a step by ID."""
        return self.steps.get(step_id)

    def recompute_roots(self) -> None:
        """Recompute ``roots`` from the current ``steps`` dict.

        A root is any step that is not referenced as the ``primary_input``
        or ``secondary_input`` of another step.  Call this after bulk
        mutations (delete, hydration) where incremental root tracking is
        impractical.
        """
        referenced: set[str] = set()
        for step in self.steps.values():
            primary = getattr(getattr(step, "primary_input", None), "id", None)
            secondary = getattr(getattr(step, "secondary_input", None), "id", None)
            if isinstance(primary, str) and primary:
                referenced.add(primary)
            if isinstance(secondary, str) and secondary:
                referenced.add(secondary)
        self.roots = {sid for sid in self.steps if sid not in referenced}

    def save_history(self, description: str) -> None:
        """Save current state to history."""
        if self.current_strategy:
            self.history.append(
                {
                    "description": description,
                    "strategy": self.current_strategy.to_dict(),
                }
            )

    def undo(self) -> bool:
        """Undo to previous state."""
        if len(self.history) < 2:
            return False
        self.history.pop()  # remove current
        previous = self.history[-1]
        strategy_value = previous.get("strategy")
        if isinstance(strategy_value, dict):
            self.current_strategy = from_dict(as_json_object(strategy_value))
        return True


class StrategySession:
    """Session context for the active strategy (graph + chat)."""

    def __init__(self, site_id: str) -> None:
        self.site_id = site_id
        self.graph: StrategyGraph | None = None

    def add_graph(self, graph: StrategyGraph) -> None:
        """Register an existing graph in the session."""
        if self.graph and self.graph.id != graph.id:
            return
        self.graph = graph

    def create_graph(self, name: str, graph_id: str | None = None) -> StrategyGraph:
        """Create a new empty graph and register it."""
        if self.graph:
            if name and name != self.graph.name:
                self.graph.name = name
            return self.graph
        new_id = graph_id or str(uuid4())
        graph = StrategyGraph(new_id, name, self.site_id)
        self.graph = graph
        return graph

    def get_graph(self, graph_id: str | None) -> StrategyGraph | None:
        """Get graph by ID (or active graph if None)."""
        if not self.graph:
            return None
        if graph_id is None or graph_id == self.graph.id:
            return self.graph
        return None


def hydrate_graph_from_steps_data(
    graph: StrategyGraph,
    steps_data: JSONArray | None,
    *,
    root_step_id: str | None = None,
    record_type: str | None = None,
) -> None:
    """Hydrate an in-memory graph from persisted flat steps.

    This is used when we have a persisted `steps` list (and maybe `root_step_id`) but
    no canonical `plan` to parse into an AST. It enables tools like `list_current_steps`
    to reflect existing UI-visible nodes.
    """
    if not steps_data or not isinstance(steps_data, list):
        return

    def _parse_filters(raw: JSONValue) -> list[StepFilter]:
        items = raw if isinstance(raw, list) else []
        filters: list[StepFilter] = []
        for item in items:
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

    def _parse_analyses(raw: JSONValue) -> list[StepAnalysis]:
        items = raw if isinstance(raw, list) else []
        analyses: list[StepAnalysis] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            analysis_type = item.get("analysisType") or item.get("analysis_type")
            if not analysis_type:
                continue
            parameters_value = item.get("parameters")
            parameters: JSONObject = (
                as_json_object(parameters_value)
                if isinstance(parameters_value, dict)
                else {}
            )
            custom_name_value = item.get("customName") or item.get("custom_name")
            custom_name: str | None = (
                str(custom_name_value) if custom_name_value is not None else None
            )
            analyses.append(
                StepAnalysis(
                    analysis_type=str(analysis_type),
                    parameters=parameters,
                    custom_name=custom_name,
                )
            )
        return analyses

    def _parse_reports(raw: JSONValue) -> list[StepReport]:
        items = raw if isinstance(raw, list) else []
        reports: list[StepReport] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            report_name = (
                item.get("reportName") or item.get("report_name") or "standard"
            )
            config_value = item.get("config")
            config: JSONObject = (
                as_json_object(config_value) if isinstance(config_value, dict) else {}
            )
            reports.append(
                StepReport(
                    report_name=str(report_name),
                    config=config,
                )
            )
        return reports

    nodes: dict[str, PlanStepNode] = {}

    for step in steps_data:
        if not isinstance(step, dict):
            continue
        step_id = step.get("id")
        if step_id is None:
            continue
        step_id = str(step_id)
        if not step_id:
            continue

        kind = str(step.get("kind") or "").strip().lower()
        search_name = step.get("searchName")
        if not isinstance(search_name, str) or not search_name:
            search_name = "__combine__" if kind == "combine" else "__unknown__"

        parameters_raw = step.get("parameters")
        parameters: JSONObject = (
            parameters_raw if isinstance(parameters_raw, dict) else {}
        )
        display_name = step.get("displayName")
        if not isinstance(display_name, str) or not display_name.strip():
            display_name = search_name

        node = PlanStepNode(
            search_name=search_name,
            parameters=parameters,
            display_name=display_name,
            id=step_id,
        )

        node.filters = _parse_filters(step.get("filters"))
        node.analyses = _parse_analyses(step.get("analyses"))
        node.reports = _parse_reports(step.get("reports"))

        op_raw = step.get("operator")
        if isinstance(op_raw, str) and op_raw:
            try:
                node.operator = CombineOp(op_raw)
            except Exception:
                node.operator = None

        cp_raw = step.get("colocationParams")
        if isinstance(cp_raw, dict):
            cp_dict = as_json_object(cp_raw)
            upstream_value = cp_dict.get("upstream", 0)
            downstream_value = cp_dict.get("downstream", 0)
            strand_value = cp_dict.get("strand", "both")
            upstream = (
                int(upstream_value) if isinstance(upstream_value, (int, float)) else 0
            )
            downstream = (
                int(downstream_value)
                if isinstance(downstream_value, (int, float))
                else 0
            )
            strand_str = str(strand_value) if strand_value is not None else "both"
            from typing import Literal

            if strand_str == "same":
                strand: Literal["same", "opposite", "both"] = "same"
            elif strand_str == "opposite":
                strand = "opposite"
            else:
                strand = "both"
            node.colocation_params = ColocationParams(
                upstream=upstream,
                downstream=downstream,
                strand=strand,
            )

        nodes[step_id] = node

    # Second pass: connect inputs.
    for step in steps_data:
        if not isinstance(step, dict):
            continue
        step_id = step.get("id")
        if step_id is None:
            continue
        current_node: PlanStepNode | None = nodes.get(str(step_id))
        if current_node is None:
            continue
        primary_id = step.get("primaryInputStepId")
        secondary_id = step.get("secondaryInputStepId")
        if primary_id is not None:
            primary_node = nodes.get(str(primary_id))
            if primary_node is not None:
                current_node.primary_input = primary_node
        if secondary_id is not None:
            secondary_node = nodes.get(str(secondary_id))
            if secondary_node is not None:
                current_node.secondary_input = secondary_node

    # Attach hydrated nodes to the graph (don't blow away any already-loaded plan steps).
    if not graph.steps:
        graph.steps = nodes
    else:
        for sid, node in nodes.items():
            graph.steps.setdefault(sid, node)

    # Best-effort record type context.
    if record_type and not graph.record_type:
        graph.record_type = record_type
    if not graph.record_type:
        for step in steps_data:
            if isinstance(step, dict) and step.get("recordType"):
                graph.record_type = str(step.get("recordType"))
                break

    # Recompute the subtree-root set from the hydrated step graph.
    graph.recompute_roots()

    # Best-effort last-step pointer (used for plan emission / backward compat).
    if root_step_id and str(root_step_id) in graph.steps:
        graph.last_step_id = str(root_step_id)
    elif len(graph.roots) == 1:
        graph.last_step_id = next(iter(graph.roots))
    elif not graph.last_step_id and graph.roots:
        # Pick an arbitrary root when multiple exist.
        graph.last_step_id = next(iter(graph.roots))

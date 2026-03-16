"""Stateful strategy session types (in-memory).

These types model the *working* state while a user (or an AI agent) is building a
VEuPathDB strategy during a chat session.
"""

from uuid import uuid4

from veupath_chatbot.domain.strategy.ast import (
    PlanStepNode,
    StrategyAST,
    from_dict,
    parse_analyses,
    parse_colocation_params,
    parse_filters,
    parse_reports,
)
from veupath_chatbot.domain.strategy.ops import CombineOp
from veupath_chatbot.platform.types import (
    JSONArray,
    JSONObject,
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

        :param step: Step to add.
        :returns: Step ID.
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
        """Get a step by ID.

        :param step_id: Step ID.
        :returns: Step or None.
        """
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
        """Save current state to history.

        :param description: Description of the state.
        """
        if self.current_strategy:
            self.history.append(
                {
                    "description": description,
                    "strategy": self.current_strategy.to_dict(),
                }
            )

    def undo(self) -> bool:
        """Undo to previous state.

        Restores ``current_strategy`` **and** the derived graph state
        (``steps``, ``roots``, ``last_step_id``) so that tools that inspect
        the step graph see a consistent picture after undo.
        """
        if len(self.history) < 2:
            return False
        self.history.pop()  # remove current
        previous = self.history[-1]
        strategy_value = previous.get("strategy")
        if isinstance(strategy_value, dict):
            self.current_strategy = from_dict(as_json_object(strategy_value))
            self.steps = {s.id: s for s in self.current_strategy.get_all_steps()}
            self.recompute_roots()
            self.last_step_id = self.current_strategy.root.id
        return True


class StrategySession:
    """Session context for the active strategy (graph + chat)."""

    def __init__(self, site_id: str) -> None:
        self.site_id = site_id
        self.graph: StrategyGraph | None = None

    def add_graph(self, graph: StrategyGraph) -> None:
        """Register an existing graph in the session.

        :param graph: Strategy graph to register.
        """
        if self.graph and self.graph.id != graph.id:
            return
        self.graph = graph

    def create_graph(self, name: str, graph_id: str | None = None) -> StrategyGraph:
        """Create a new empty graph and register it.

        :param name: Graph name.
        :param graph_id: Optional graph ID (default: None).
        :returns: The graph.
        """
        if self.graph:
            if name and name != self.graph.name:
                self.graph.name = name
            return self.graph
        new_id = graph_id or str(uuid4())
        graph = StrategyGraph(new_id, name, self.site_id)
        self.graph = graph
        return graph

    def get_graph(self, graph_id: str | None) -> StrategyGraph | None:
        """Get graph by ID (or active graph if None).

        :param graph_id: Graph ID, or None for active graph.
        :returns: Graph or None.
        """
        if not self.graph:
            return None
        if graph_id is None or graph_id == self.graph.id:
            return self.graph
        return None


def hydrate_graph_from_steps_data(
    graph: StrategyGraph,
    steps_data: JSONArray | object,
    *,
    root_step_id: str | None = None,
    record_type: str | None = None,
) -> None:
    """Hydrate an in-memory graph from persisted flat steps.

    This is used when we have a persisted `steps` list (and maybe `root_step_id`) but
    no canonical `plan` to parse into an AST. It enables tools like `list_current_steps`
    to reflect existing UI-visible nodes.

    Accepts arbitrary input; non-list values are silently ignored.

    :param graph: Strategy graph to hydrate.
    :param steps_data: Flat steps list from persistence (or any value).
    :param root_step_id: Root step ID (default: None).
    :param record_type: Record type (default: None).
    """
    if not steps_data or not isinstance(steps_data, list):
        return

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

        node.filters = parse_filters(step.get("filters"))
        node.analyses = parse_analyses(step.get("analyses"))
        node.reports = parse_reports(step.get("reports"))

        op_raw = step.get("operator")
        if isinstance(op_raw, str) and op_raw:
            try:
                node.operator = CombineOp(op_raw)
            except Exception:
                node.operator = None

        node.colocation_params = parse_colocation_params(step.get("colocationParams"))

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

    # Restore WDK build state from persisted per-step fields.
    for step in steps_data:
        if not isinstance(step, dict):
            continue
        sid_raw = step.get("id")
        if sid_raw is None:
            continue
        sid = str(sid_raw)
        wdk_step_id = step.get("wdkStepId")
        if isinstance(wdk_step_id, int):
            graph.wdk_step_ids[sid] = wdk_step_id
        result_count = step.get("resultCount")
        if isinstance(result_count, int):
            graph.step_counts[sid] = result_count

    # Recompute the subtree-root set from the hydrated step graph.
    graph.recompute_roots()

    # Best-effort last-step pointer (used for plan emission when roots is ambiguous).
    if root_step_id and str(root_step_id) in graph.steps:
        graph.last_step_id = str(root_step_id)
    elif len(graph.roots) == 1:
        graph.last_step_id = next(iter(graph.roots))
    elif not graph.last_step_id and graph.roots:
        # Pick an arbitrary root when multiple exist.
        graph.last_step_id = next(iter(graph.roots))

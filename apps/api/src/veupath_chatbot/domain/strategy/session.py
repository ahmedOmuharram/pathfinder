"""Stateful strategy session types (in-memory).

These types model the *working* state while a user (or an AI agent) is building a
VEuPathDB strategy during a chat session.
"""

from uuid import uuid4

from veupath_chatbot.domain.strategy.ast import (
    PlanStepNode,
    StrategyAST,
)
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKValidation
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import (
    JSONObject,
    as_json_object,
)

logger = get_logger(__name__)

_MIN_UNDO_HISTORY = 2


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
        self.steps: dict[str, PlanStepNode] = {}
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
        # Populated after build_strategy — maps local step IDs to WDK validation.
        self.step_validations: dict[str, WDKValidation] = {}
        # WDK strategy ID, set after build_strategy creates the strategy on WDK.
        self.wdk_strategy_id: int | None = None

    def invalidate_build(self) -> None:
        """Clear WDK build state so stale counts are not shown.

        Call after any mutation that changes step semantics (parameters,
        search_name, operator, delete).  The next ``build_strategy`` call
        will re-populate ``step_counts`` and ``wdk_step_ids``.
        """
        self.step_counts.clear()
        self.wdk_step_ids.clear()
        self.step_validations.clear()
        self.wdk_strategy_id = None
        self.current_strategy = None

    def add_step(self, step: PlanStepNode) -> str:
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

    def get_step(self, step_id: str) -> PlanStepNode | None:
        """Get a step by ID.

        :param step_id: Step ID.
        :returns: Step or None.
        """
        return self.steps.get(step_id)

    def find_consumer(self, step_id: str) -> str | None:
        """Find the step that consumes *step_id* as a primary or secondary input.

        :param step_id: Step ID to search for.
        :returns: ID of the consuming step, or None if unconsumed.
        """
        for s in self.steps.values():
            if (s.primary_input and s.primary_input.id == step_id) or (
                s.secondary_input and s.secondary_input.id == step_id
            ):
                return s.id
        return None

    def recompute_roots(self) -> None:
        """Recompute ``roots`` from the current ``steps`` dict.

        A root is any step that is not referenced as the ``primary_input``
        or ``secondary_input`` of another step.  Call this after bulk
        mutations (delete, hydration) where incremental root tracking is
        impractical.
        """
        referenced: set[str] = set()
        for step in self.steps.values():
            if step.primary_input:
                referenced.add(step.primary_input.id)
            if step.secondary_input:
                referenced.add(step.secondary_input.id)
        self.roots = {sid for sid in self.steps if sid not in referenced}

    def save_history(self, description: str) -> None:
        """Save current state to history.

        :param description: Description of the state.
        """
        if self.current_strategy:
            self.history.append(
                {
                    "description": description,
                    "strategy": self.current_strategy.model_dump(
                        by_alias=True, exclude_none=True, mode="json"
                    ),
                }
            )

    def undo(self) -> bool:
        """Undo to previous state.

        Restores ``current_strategy`` **and** the derived graph state
        (``steps``, ``roots``, ``last_step_id``) so that tools that inspect
        the step graph see a consistent picture after undo.
        """
        if len(self.history) < _MIN_UNDO_HISTORY:
            return False
        self.history.pop()  # remove current
        previous = self.history[-1]
        strategy_value = previous.get("strategy")
        if isinstance(strategy_value, dict):
            self.current_strategy = StrategyAST.model_validate(
                as_json_object(strategy_value)
            )
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

        Logs a warning if a different graph is already active (the new graph
        is ignored to avoid silently discarding in-progress work).

        :param graph: Strategy graph to register.
        """
        if self.graph and self.graph.id != graph.id:
            logger.warning(
                "Ignoring add_graph: session already has an active graph",
                active_graph_id=self.graph.id,
                rejected_graph_id=graph.id,
            )
            return
        self.graph = graph

    def create_graph(self, name: str, graph_id: str | None = None) -> StrategyGraph:
        """Create a new empty graph, or return the existing one.

        When a graph already exists the session reuses it (single-graph
        model). The name is updated if it differs.

        :param name: Graph name.
        :param graph_id: Optional graph ID (default: None).
        :returns: The graph.
        """
        if self.graph:
            if name and name != self.graph.name:
                logger.debug(
                    "Reusing existing graph with updated name",
                    graph_id=self.graph.id,
                    old_name=self.graph.name,
                    new_name=name,
                )
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

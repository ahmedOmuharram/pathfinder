"""Stateful strategy session types (in-memory).

These types model the *working* state while a user (or an AI agent) is building a
VEuPathDB strategy during a chat session.
"""

from uuid import uuid4

from pathfinder.domain.strategy.ast import (
    COMBINE_SEARCH_NAME,
    StrategyStepNode,
    walk_step_tree,
)
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.strategy_ast import StrategyAst, _HistoryEntry
from pathfinder.domain.strategy.types import SyncStateProtocol
from pathfinder.domain.strategy.validation import StepValidation
from pathfinder.platform.logging import get_logger

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
        self.description: str | None = None
        self.steps: dict[str, StrategyStepNode] = {}
        # Current subtree root IDs.  Every step creation updates this set:
        # the new step is added as a root and any inputs it consumes are
        # removed.  A complete strategy has exactly one root.
        self.roots: set[str] = set()
        self.history: list[_HistoryEntry] = []
        self.last_step_id: str | None = None

    def to_strategy_ast(
        self,
        root_step_id: str | None = None,
        sync_state: SyncStateProtocol | None = None,
    ) -> StrategyAst | None:
        """Produce a typed plan payload for API responses and DB persistence."""
        root_id = root_step_id or (
            next(iter(self.roots)) if len(self.roots) == 1 else None
        )
        root = self.steps.get(root_id) if root_id else None
        if root is None:
            return None

        step_counts: dict[str, int] | None = None
        wdk_step_ids: dict[str, int] | None = None
        step_validations: dict[str, StepValidation] | None = None
        if sync_state is not None:
            if sync_state.step_counts:
                step_counts = {
                    k: v for k, v in sync_state.step_counts.items() if v is not None
                }
            if sync_state.wdk_step_ids:
                wdk_step_ids = dict(sync_state.wdk_step_ids)
            if sync_state.step_validations:
                step_validations = dict(sync_state.step_validations)

        return StrategyAst(
            record_type=self.record_type or "",
            root=root,
            name=self.name,
            description=self.description or None,
            step_counts=step_counts,
            wdk_step_ids=wdk_step_ids,
            step_validations=step_validations,
        )

    def add_step(self, step: StrategyStepNode) -> str:
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
        if len(self.roots) > 1:
            logger.debug(
                "Multiple roots during construction: %d roots (%s)",
                len(self.roots),
                self.roots,
            )
        return step.id

    def find_parent(self, step_id: str) -> tuple[StrategyStepNode, str] | None:
        """Find the parent of a step and which input slot it occupies.

        :param step_id: Step ID to look up.
        :returns: ``(parent_node, 'primary' | 'secondary')`` or ``None`` if
            *step_id* is a root or does not exist.
        """
        for s in self.steps.values():
            if s.primary_input and s.primary_input.id == step_id:
                return s, "primary"
            if s.secondary_input and s.secondary_input.id == step_id:
                return s, "secondary"
        return None

    def insert_step_with_combine(
        self,
        new_step: StrategyStepNode,
        combine_with_step_id: str,
        operator: CombineOp,
        combine_display_name: str | None = None,
    ) -> tuple[str, str]:
        """Atomic leaf+combine creation maintaining the single-root invariant.

        Creates *new_step* and a combine node, inserting the combine between
        *combine_with_step_id* and its parent (or making it the new root).

        :param new_step: The new search/transform step to add.
        :param combine_with_step_id: ID of the existing step to combine with.
        :param operator: Boolean operator for the combine.
        :param combine_display_name: Optional display name for the combine node.
        :returns: ``(new_step_id, combine_step_id)``.
        :raises KeyError: If *combine_with_step_id* is not in the graph.
        """
        target = self.steps.get(combine_with_step_id)
        if target is None:
            msg = f"Step '{combine_with_step_id}' not found in graph"
            raise KeyError(msg)

        # Find the parent BEFORE adding new nodes (otherwise the combine
        # itself would be returned as the parent of the target).
        parent_info = self.find_parent(combine_with_step_id)

        # Register the new leaf in the graph.
        self.steps[new_step.id] = new_step

        # Create the combine node.
        combine = StrategyStepNode(
            search_name=COMBINE_SEARCH_NAME,
            primary_input=target,
            secondary_input=new_step,
            operator=operator,
            display_name=combine_display_name or str(operator.value),
        )
        self.steps[combine.id] = combine

        # Splice the combine between the target and its parent.
        if parent_info is not None:
            parent, slot = parent_info
            if slot == "primary":
                parent.primary_input = combine
            else:
                parent.secondary_input = combine
        # Otherwise target was a root — combine replaces it.

        self.recompute_roots()
        self.last_step_id = combine.id
        self.save_history(f"Combined {new_step.id} with {combine_with_step_id}")
        return new_step.id, combine.id

    def get_step(self, step_id: str) -> StrategyStepNode | None:
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
        """Save current state to history."""
        ast = self.to_strategy_ast()
        if ast is not None:
            self.history.append(
                _HistoryEntry(description=description, strategy_ast=ast),
            )

    def undo(self) -> bool:
        """Undo to previous state.

        Restores steps, roots, and last_step_id from the history snapshot.
        """
        if len(self.history) < _MIN_UNDO_HISTORY:
            return False
        self.history.pop()  # remove current
        previous = self.history[-1]
        root = previous.strategy_ast.root
        all_steps = walk_step_tree(root)
        self.steps = {s.id: s for s in all_steps}
        self.recompute_roots()
        self.last_step_id = root.id
        return True


class StrategySession:
    """Session context for the active strategy (graph + chat)."""

    def __init__(self, site_id: str) -> None:
        self.site_id = site_id
        self.graph: StrategyGraph | None = None
        self.sync_state: SyncStateProtocol | None = None

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

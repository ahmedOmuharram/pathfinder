"""Stateful strategy session types (in-memory).

These types model the *working* state while a user (or an AI agent) is building a
VEuPathDB strategy during a chat session.
"""

from uuid import uuid4

from veupath_chatbot.domain.strategy.ast import (
    COMBINE_SEARCH_NAME,
    PlanStepNode,
    walk_step_tree,
)
from veupath_chatbot.domain.strategy.ops import CombineOp
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKStepTree, WDKValidation
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject

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
        # WDK step tree, set after push to WDK.
        self.wdk_step_tree: WDKStepTree | None = None
        # Maps local step ID → push error message when WDK rejects a step.
        # Surfaced to the model so it can fix params or delete the step.
        self.wdk_push_errors: dict[str, str] = {}

    def to_plan(self, root_step_id: str | None = None) -> JSONObject:
        """Produce the plan dict for API responses and DB persistence."""
        root_id = root_step_id or (
            next(iter(self.roots)) if len(self.roots) == 1 else None
        )
        root = self.steps.get(root_id) if root_id else None
        if root is None:
            return {}
        plan: JSONObject = {
            "recordType": self.record_type or "",
            "root": root.model_dump(by_alias=True, exclude_none=True, mode="json"),
            "name": self.name,
        }
        if self.description:
            plan["description"] = self.description
        if self.step_counts:
            plan["stepCounts"] = {
                k: v for k, v in self.step_counts.items() if v is not None
            }
        if self.wdk_step_ids:
            plan["wdkStepIds"] = dict(self.wdk_step_ids)
        return plan

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
        if len(self.roots) > 1:
            logger.debug(
                "Multiple roots during construction: %d roots (%s)",
                len(self.roots),
                self.roots,
            )
        return step.id

    def find_parent(self, step_id: str) -> tuple[PlanStepNode, str] | None:
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
        new_step: PlanStepNode,
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
        combine = PlanStepNode(
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

    def delete_step_connected(self, step_id: str) -> list[str]:
        """Delete a step while maintaining the single-root invariant.

        Semantics by step kind:

        - **Leaf of a combine**: remove the leaf AND the parent combine;
          reconnect the sibling to the grandparent.
        - **Transform**: remove the transform; reconnect its input to its
          consumer.
        - **Subtree (combine or leaf) child of a combine**: remove the entire
          subtree plus the parent combine; keep the sibling.
        - **Sole step / root leaf**: empty the graph.
        - **Root combine**: keep primary subtree, delete secondary + combine.

        :param step_id: ID of the step to delete.
        :returns: List of deleted step IDs.
        """
        step = self.steps.get(step_id)
        if step is None:
            return []

        kind = step.infer_kind()
        parent_info = self.find_parent(step_id)

        # --- Case: deleting a transform → skip it, reconnect input to consumer ---
        if kind == "transform":
            input_step = step.primary_input
            if parent_info is not None:
                parent, slot = parent_info
                if slot == "primary":
                    parent.primary_input = input_step
                else:
                    parent.secondary_input = input_step
            del self.steps[step_id]
            self.recompute_roots()
            self.last_step_id = next(iter(self.roots), None)
            return [step_id]

        # --- Case: no parent (root) ---
        if parent_info is None:
            return self._delete_root_step(step_id, step, kind)

        # --- Case: step has a parent ---
        parent, slot = parent_info
        parent_kind = parent.infer_kind()

        if parent_kind == "combine":
            return self._collapse_parent_combine(step, parent, slot)

        if parent_kind == "transform":
            # Step is the input of a transform. Deleting it leaves the
            # transform dangling, so cascade: delete step subtree, then
            # recursively delete the parent transform.
            subtree_ids = {s.id for s in walk_step_tree(step)}
            for sid in subtree_ids:
                self.steps.pop(sid, None)
            parent.primary_input = None
            return sorted(subtree_ids) + self.delete_step_connected(parent.id)

        # Fallback (shouldn't reach here under normal usage).
        subtree_ids_fb = {s.id for s in walk_step_tree(step)}
        for sid in subtree_ids_fb:
            self.steps.pop(sid, None)
        self.recompute_roots()
        self.last_step_id = next(iter(self.roots), None)
        return sorted(subtree_ids_fb)

    def _collapse_parent_combine(
        self, step: PlanStepNode, parent: PlanStepNode, slot: str
    ) -> list[str]:
        """Collapse a parent combine: keep sibling, delete step subtree + combine."""
        sibling = parent.secondary_input if slot == "primary" else parent.primary_input

        # Reconnect sibling to grandparent.
        grandparent_info = self.find_parent(parent.id)
        if grandparent_info is not None:
            grandparent, gp_slot = grandparent_info
            if gp_slot == "primary":
                grandparent.primary_input = sibling
            else:
                grandparent.secondary_input = sibling

        # Collect all IDs in the deleted subtree.
        subtree_ids = {s.id for s in walk_step_tree(step)}
        to_delete = subtree_ids | {parent.id}
        for sid in to_delete:
            self.steps.pop(sid, None)
        self.recompute_roots()
        self.last_step_id = next(iter(self.roots), None)
        return sorted(to_delete)

    def _delete_root_step(
        self, step_id: str, step: PlanStepNode, kind: str
    ) -> list[str]:
        """Handle deletion of a root step (no parent)."""
        if kind == "search":
            # Sole leaf — empty the graph.
            deleted = list(self.steps)
            self.steps.clear()
            self.roots.clear()
            self.last_step_id = None
            return deleted

        if kind == "combine":
            # Root combine: keep primary subtree, delete secondary + combine.
            primary = step.primary_input
            secondary = step.secondary_input
            sec_ids: set[str] = (
                {s.id for s in walk_step_tree(secondary)} if secondary else set()
            )
            to_delete = sec_ids | {step_id}
            for sid in to_delete:
                self.steps.pop(sid, None)
            self.recompute_roots()
            self.last_step_id = (
                primary.id if primary else next(iter(self.roots), None)
            )
            return sorted(to_delete)

        # Root transform (unlikely but handle gracefully): promote input.
        if kind == "transform" and step.primary_input:
            del self.steps[step_id]
            self.recompute_roots()
            self.last_step_id = step.primary_input.id
            return [step_id]

        # Empty or unknown — clear everything.
        deleted_all = list(self.steps)
        self.steps.clear()
        self.roots.clear()
        self.last_step_id = None
        return deleted_all

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
        """Save current state to history."""
        plan = self.to_plan()
        if plan:
            self.history.append({"description": description, "plan": plan})

    def undo(self) -> bool:
        """Undo to previous state.

        Restores steps, roots, and last_step_id from the history snapshot.
        Handles both new plan-format and old AST-format entries for migration.
        """
        if len(self.history) < _MIN_UNDO_HISTORY:
            return False
        self.history.pop()  # remove current
        previous = self.history[-1]

        # New format: {"plan": {...}}
        plan_value = previous.get("plan")
        if isinstance(plan_value, dict) and "root" in plan_value:
            root = PlanStepNode.model_validate(plan_value["root"])
            all_steps = walk_step_tree(root)
            self.steps = {s.id: s for s in all_steps}
            self.recompute_roots()
            self.last_step_id = root.id
            return True

        # Old format entries are no longer supported (StrategyAST removed).
        return False


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

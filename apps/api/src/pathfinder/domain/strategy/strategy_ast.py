"""Strategy AST: the canonical typed representation of a built/buildable strategy.

``StrategyAst`` is the serialized graph state (root ``StrategyStepNode`` tree,
step counts, WDK step IDs, metadata). It is the output of both the planning
phase (declarative tree the agent produces) and the execution phase (the
materialized state with ``wdk_step_ids`` populated). The UI renders it as
``StrategyGraph``.

The single-root invariant is enforced: every strategy must reduce to one
root step matching WDK's stepTree shape. Multi-root state is invalid.
"""

from pydantic import ConfigDict, model_validator

from pathfinder.domain.strategy.ast import StrategyStepNode, walk_step_tree
from pathfinder.domain.strategy.validation import StepValidation
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.platform.types import JSONObject


class StrategyAst(CamelModel):
    """Serialized strategy graph state used at every persistence boundary."""

    record_type: str
    root: StrategyStepNode
    name: str | None = None
    description: str | None = None
    metadata: JSONObject | None = None
    step_counts: dict[str, int] | None = None
    wdk_step_ids: dict[str, int] | None = None
    step_validations: dict[str, StepValidation] | None = None

    @model_validator(mode="after")
    def _validate_single_root_and_unique_ids(self) -> "StrategyAst":
        """Reject duplicate step ids in the tree.

        Single-root is structurally guaranteed by ``root: StrategyStepNode``
        (one node, recursive children). This validator catches the other
        WDK-incompatible shape: the same step id appearing in two positions
        of the tree (which would also fail WDK's "step belongs to one
        strategy" invariant on push).
        """
        nodes = walk_step_tree(self.root)
        seen: set[str] = set()
        duplicates: set[str] = set()
        for node in nodes:
            if node.id in seen:
                duplicates.add(node.id)
            seen.add(node.id)
        if duplicates:
            msg = (
                f"strategy contains duplicate step ids: {sorted(duplicates)}; "
                "every step in the tree must have a unique id"
            )
            raise ValueError(msg)
        return self


class PersistedStrategyGraph(CamelModel):
    """Outer container shape for strategy AST snapshots.

    Parsed at the load boundary via model_validate() so downstream code gets
    typed attribute access instead of isinstance guards on JSONObject dicts.
    """

    model_config = ConfigDict(extra="ignore")

    id: str | None = None
    graph_id: str | None = None
    name: str | None = None
    strategy_ast: StrategyAst | None = None
    record_type: str | None = None
    wdk_strategy_id: int | None = None


class _HistoryEntry(CamelModel):
    """Internal: typed undo history entry for StrategyGraph.

    Transient (not persisted — rebuilt on load).
    """

    description: str
    strategy_ast: StrategyAst

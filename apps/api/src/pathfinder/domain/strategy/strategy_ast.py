"""Strategy AST: the canonical typed representation of a built/buildable strategy.

``StrategyAst`` is the serialized graph state (root ``StrategyStepNode`` tree,
step counts, WDK step IDs, metadata). It is the *output* of the execution
phase — a compiled recipe that the UI renders as ``StrategyGraph``.

This is NOT the AI planning artifact produced by the planning agent — see
``domain/strategy/plan.StrategyPlan`` for that, which is a separate
user-facing proposal (approve/reject card) with no persistence path.
"""

from pydantic import ConfigDict

from pathfinder.domain.strategy.ast import StrategyStepNode
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

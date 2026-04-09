"""Typed plan payloads for strategy persistence and SSE events.

StrategyPlanPayload is the canonical typed representation of a strategy
plan — the serialized graph state (root PlanStepNode tree, step counts,
WDK step IDs, metadata).  All code that previously used JSONObject for
plan data should use this model instead.

PersistedStrategyGraph is the outer container shape stored in Redis.
_HistoryEntry is internal to StrategyGraph for typed undo history.
"""

from pydantic import ConfigDict

from pathfinder.domain.strategy.ast import PlanStepNode
from pathfinder.domain.strategy.validation import StepValidation
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.platform.types import JSONObject


class StrategyPlanPayload(CamelModel):
    """Canonical typed plan: the serialized graph state.

    Used for API request/response, Redis persistence, and SSE events.
    NOT the AI planning artifact (see domain/strategy/plan.py:StrategyPlan).
    """

    record_type: str
    root: PlanStepNode
    name: str | None = None
    description: str | None = None
    metadata: JSONObject | None = None
    step_counts: dict[str, int] | None = None
    wdk_step_ids: dict[str, int] | None = None
    step_validations: dict[str, StepValidation] | None = None


class PersistedStrategyGraph(CamelModel):
    """Outer container shape for strategy graphs stored in Redis.

    Parsed at the Redis load boundary via model_validate() so that
    downstream code gets typed attribute access instead of isinstance
    guards on JSONObject dicts.
    """

    model_config = ConfigDict(extra="ignore")

    id: str | None = None
    graph_id: str | None = None
    name: str | None = None
    plan: StrategyPlanPayload | None = None
    record_type: str | None = None
    wdk_strategy_id: int | None = None


class _HistoryEntry(CamelModel):
    """Internal: typed undo history entry for StrategyGraph.

    Transient (not persisted to Redis — rebuilt on load).
    """

    description: str
    plan: StrategyPlanPayload

"""Conversation tool response models and helpers."""

from __future__ import annotations

from pathfinder.domain.strategy.session import StrategyGraph
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.platform.types import JSONObject


class RenameStrategyResult(CamelModel):
    """Result of renaming a strategy."""

    graph_id: str
    old_name: str
    new_name: str
    name: str
    record_type: str
    description: str
    plan: JSONObject | None = None


class ClearStrategyResult(CamelModel):
    """Result of clearing a strategy."""

    graph_id: str
    message: str


def _has_strategy(graph: StrategyGraph) -> bool:
    """Check whether a graph has any strategy content."""
    return bool(graph.steps or graph.wdk_strategy_id)

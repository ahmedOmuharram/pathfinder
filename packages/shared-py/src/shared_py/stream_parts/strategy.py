"""Typed payloads for strategy data-parts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from shared_py.pydantic_base import CamelModel

StrategyOperation = Literal[
    "add_step", "remove_step", "update_step", "replace_step_tree"
]


class StrategyPatch(CamelModel):
    """A partial update to a strategy, emitted by strategy-mutating tools."""

    strategy_id: str
    operation: StrategyOperation
    step: dict[str, Any] | None = None  # StepResponse-shaped
    step_tree: dict[str, Any] | None = None  # StepTree-shaped


class StrategyMeta(CamelModel):
    """Top-level strategy metadata (one per strategy creation/load)."""

    strategy_id: str
    name: str
    is_saved: bool
    estimated_size: int = Field(ge=0)
    record_class_name: str


class StrategyLink(CamelModel):
    """A link to the strategy in the public WDK UI."""

    strategy_id: str
    url: str = Field(pattern=r"^https?://")
    title: str | None = None

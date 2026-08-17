"""Authoritative read of the strategy as it exists right now.

The Ledger holds counts from the last build. Anything the user changed since
then — a parameter edited in the graph editor, a step deleted in the WDK web
UI — is invisible to it. This module reads the same live session the UI reads,
so the Lead can answer "what does my strategy return now?" with a fact rather
than a memory.
"""

from pydantic import Field

from pathfinder.ai.tools.standalone._graph_helpers import build_step_response
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.platform.pydantic_base import CamelModel

__all__ = ["LiveStepState", "LiveStrategyState", "read_live_state"]


class LiveStepState(CamelModel):
    step_id: str
    display_name: str
    search_name: str | None = None
    estimated_size: int | None = None
    parameters: dict[str, object] = Field(default_factory=dict)


class LiveStrategyState(CamelModel):
    """What the strategy actually is, read fresh from the session."""

    wdk_strategy_id: int | None = None
    step_count: int = 0
    root_count: int | None = None
    steps: list[LiveStepState] = Field(default_factory=list)


def read_live_state(session: StrategySession) -> LiveStrategyState:
    """Snapshot the live strategy for the Lead."""
    graph = session.graph
    if graph is None:
        return LiveStrategyState()

    sync_state = session.sync_state
    steps = [
        LiveStepState(
            step_id=step.id,
            display_name=response.display_name or step.id,
            search_name=response.search_name,
            estimated_size=response.estimated_size,
            parameters=dict(step.parameters or {}),
        )
        for step in graph.steps.values()
        if (response := build_step_response(graph, step, sync_state)) is not None
    ]
    # A complete strategy has exactly one root; ambiguity means no single
    # headline count to report.
    root_count = None
    if sync_state is not None and len(graph.roots) == 1:
        raw = sync_state.step_counts.get(next(iter(graph.roots)))
        root_count = raw if isinstance(raw, int) else None

    return LiveStrategyState(
        wdk_strategy_id=sync_state.wdk_strategy_id if sync_state else None,
        step_count=len(graph.steps),
        root_count=root_count,
        steps=steps,
    )

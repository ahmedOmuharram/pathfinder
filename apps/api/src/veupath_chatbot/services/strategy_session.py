"""Stateful strategy session types (in-memory).

These types model the *working* state while a user (or an AI agent) is building a
VEuPathDB strategy during a chat session.

They are intentionally **not** part of the pure domain layer:
- They hold mutable state (steps/history/current draft strategy)
- They represent an application/session concept (chat + graph = strategy session)
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from veupath_chatbot.domain.strategy.ast import (
    PlanStepNode,
    StrategyAST,
    from_dict,
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
        self.history: list[dict[str, Any]] = []
        self.last_step_id: str | None = None

    def add_step(self, step: Step) -> str:
        """Add a step to the graph."""
        self.steps[step.id] = step
        self.last_step_id = step.id
        return step.id

    def get_step(self, step_id: str) -> Step | None:
        """Get a step by ID."""
        return self.steps.get(step_id)

    def save_history(self, description: str) -> None:
        """Save current state to history."""
        if self.current_strategy:
            self.history.append(
                {
                    "description": description,
                    "strategy": self.current_strategy.to_dict(),
                }
            )

    def undo(self) -> bool:
        """Undo to previous state."""
        if len(self.history) < 2:
            return False
        self.history.pop()  # remove current
        previous = self.history[-1]
        self.current_strategy = from_dict(previous["strategy"])
        return True


class StrategySession:
    """Session context for the active strategy (graph + chat)."""

    def __init__(self, site_id: str) -> None:
        self.site_id = site_id
        self.graph: StrategyGraph | None = None

    def add_graph(self, graph: StrategyGraph) -> None:
        """Register an existing graph in the session."""
        if self.graph and self.graph.id != graph.id:
            return
        self.graph = graph

    def create_graph(self, name: str, graph_id: str | None = None) -> StrategyGraph:
        """Create a new empty graph and register it."""
        if self.graph:
            if name and name != self.graph.name:
                self.graph.name = name
            return self.graph
        new_id = graph_id or str(uuid4())
        graph = StrategyGraph(new_id, name, self.site_id)
        self.graph = graph
        return graph

    def get_graph(self, graph_id: str | None) -> StrategyGraph | None:
        """Get graph by ID (or active graph if None)."""
        if not self.graph:
            return None
        if graph_id is None or graph_id == self.graph.id:
            return self.graph
        return None


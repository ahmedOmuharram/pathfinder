"""Graph inspection tools (AI-exposed)."""

from __future__ import annotations

from typing import Any

from kani import ai_function


class StrategyGraphOps:
    """Graph inspection tools."""

    @ai_function()
    async def list_graphs(self) -> list[dict[str, Any]]:
        """List graphs in the current strategy session with their steps."""
        graph = self.session.get_graph(None)
        if not graph:
            return []
        steps = [self._serialize_step(graph, step) for step in graph.steps.values()]
        return [
            {
                "graphId": graph.id,
                "graphName": graph.name,
                "stepCount": len(graph.steps),
                "steps": steps,
            }
        ]

    @ai_function()
    async def list_current_steps(self, graph_id: str | None = None) -> list[dict[str, Any]]:
        """List all steps in the current strategy context.

        Shows what steps have been created and their relationships.
        """
        graph = self._get_graph(graph_id)
        if not graph:
            return [self._graph_not_found(graph_id)]
        steps: list[dict[str, Any]] = []
        for _, step in graph.steps.items():
            steps.append(self._serialize_step(graph, step))
        return steps


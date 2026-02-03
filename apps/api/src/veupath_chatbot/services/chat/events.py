"""Semantic chat events and tool-result mapping."""

from __future__ import annotations

from typing import Any, Callable

GRAPH_SNAPSHOT = "graph_snapshot"
GRAPH_PLAN = "graph_plan"
GRAPH_CLEARED = "graph_cleared"
GRAPH_DELETED = "graph_deleted"
STRATEGY_LINK = "strategy_link"
STRATEGY_META = "strategy_meta"
STRATEGY_UPDATE = "strategy_update"


def tool_result_to_events(
    result: Any,
    *,
    get_graph: Callable[[str | None], Any] | None = None,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not isinstance(result, dict):
        return events

    if "stepId" in result:
        graph_id = result.get("graphId")
        graph = get_graph(graph_id) if get_graph else None
        events.append(
            {
                "type": STRATEGY_UPDATE,
                "data": {
                    "graphId": graph_id,
                    "step": result,
                    "allSteps": [
                        {
                            "stepId": sid,
                            # legacy compatibility: include both kind and type
                            "kind": getattr(s, "infer_kind", lambda: None)(),
                            "displayName": s.display_name,
                        }
                        for sid, s in (graph.steps.items() if graph else [])
                    ],
                },
            }
        )

    if result.get("graphSnapshot"):
        snapshot = result.get("graphSnapshot")
        graph_id = snapshot.get("graphId") if isinstance(snapshot, dict) else None
        if graph_id is None:
            graph_id = result.get("graphId")
        events.append(
            {
                "type": GRAPH_SNAPSHOT,
                "data": {"graphId": graph_id, "graphSnapshot": snapshot},
            }
        )

    if result.get("plan"):
        events.append(
            {
                "type": GRAPH_PLAN,
                "data": {
                    "graphId": result.get("graphId"),
                    "plan": result.get("plan"),
                    "name": result.get("name"),
                    "recordType": result.get("recordType"),
                    "description": result.get("description"),
                },
            }
        )

    if result.get("graphId") and (
        "name" in result or "description" in result or "recordType" in result
    ):
        events.append(
            {
                "type": STRATEGY_META,
                "data": {
                    "graphId": result.get("graphId"),
                    "name": result.get("name") or result.get("graphName"),
                    "description": result.get("description"),
                    "recordType": result.get("recordType"),
                    "graphName": result.get("graphName"),
                },
            }
        )

    if result.get("cleared"):
        events.append(
            {"type": GRAPH_CLEARED, "data": {"graphId": result.get("graphId")}}
        )

    if result.get("graphDeleted"):
        events.append(
            {"type": GRAPH_DELETED, "data": {"graphId": result.get("graphId")}}
        )

    if "wdkStrategyId" in result:
        events.append(
            {
                "type": STRATEGY_LINK,
                "data": {
                    "graphId": result.get("graphId"),
                    "wdkStrategyId": result.get("wdkStrategyId"),
                    "wdkUrl": result.get("wdkUrl"),
                    "name": result.get("name"),
                    "description": result.get("description"),
                },
            }
        )

    return events

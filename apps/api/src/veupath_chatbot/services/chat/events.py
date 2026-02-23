"""Semantic chat events and tool-result mapping."""

from __future__ import annotations

from collections.abc import Callable

from veupath_chatbot.domain.strategy.session import StrategyGraph
from veupath_chatbot.platform.types import JSONArray, JSONObject

GRAPH_SNAPSHOT = "graph_snapshot"
GRAPH_PLAN = "graph_plan"
GRAPH_CLEARED = "graph_cleared"
GRAPH_DELETED = "graph_deleted"
STRATEGY_LINK = "strategy_link"
STRATEGY_META = "strategy_meta"
STRATEGY_UPDATE = "strategy_update"
PLANNING_ARTIFACT = "planning_artifact"
CITATIONS = "citations"
REASONING = "reasoning"
PLAN_UPDATE = "plan_update"
EXECUTOR_BUILD_REQUEST = "executor_build_request"
OPTIMIZATION_PROGRESS = "optimization_progress"


def tool_result_to_events(
    result: JSONObject,
    *,
    get_graph: Callable[[str | None], StrategyGraph | None] | None = None,
) -> list[JSONObject]:
    events: list[JSONObject] = []
    if not isinstance(result, dict):
        return events

    citations = result.get("citations")
    if isinstance(citations, list) and citations:
        events.append({"type": CITATIONS, "data": {"citations": citations}})

    if result.get("planningArtifact"):
        events.append(
            {
                "type": PLANNING_ARTIFACT,
                "data": {"planningArtifact": result.get("planningArtifact")},
            }
        )

    reasoning = result.get("reasoning")
    if isinstance(reasoning, str) and reasoning.strip():
        events.append({"type": REASONING, "data": {"reasoning": reasoning}})

    conversation_title = result.get("conversationTitle")
    if isinstance(conversation_title, str) and conversation_title.strip():
        events.append({"type": PLAN_UPDATE, "data": {"title": conversation_title}})

    if isinstance(result.get("executorBuildRequest"), dict):
        events.append(
            {
                "type": EXECUTOR_BUILD_REQUEST,
                "data": {"executorBuildRequest": result.get("executorBuildRequest")},
            }
        )

    if "stepId" in result:
        graph_id_raw = result.get("graphId")
        graph_id = graph_id_raw if isinstance(graph_id_raw, str) else None
        graph = get_graph(graph_id) if get_graph else None
        all_steps: JSONArray = []
        if graph is not None:
            all_steps = [
                {
                    "stepId": sid,
                    "kind": getattr(s, "infer_kind", lambda: None)(),
                    "displayName": s.display_name,
                }
                for sid, s in graph.steps.items()
            ]
        events.append(
            {
                "type": STRATEGY_UPDATE,
                "data": {
                    "graphId": graph_id,
                    "step": result,
                    "allSteps": all_steps,
                },
            }
        )

    if result.get("graphSnapshot"):
        snapshot = result.get("graphSnapshot")
        snapshot_graph_id: str | None = None
        if isinstance(snapshot, dict):
            graph_id_raw = snapshot.get("graphId")
            snapshot_graph_id = graph_id_raw if isinstance(graph_id_raw, str) else None
        if snapshot_graph_id is None:
            graph_id_raw = result.get("graphId")
            snapshot_graph_id = graph_id_raw if isinstance(graph_id_raw, str) else None
        events.append(
            {
                "type": GRAPH_SNAPSHOT,
                "data": {"graphId": snapshot_graph_id, "graphSnapshot": snapshot},
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

    wdk_strategy_id = result.get("wdkStrategyId")
    if wdk_strategy_id is not None:
        events.append(
            {
                "type": STRATEGY_LINK,
                "data": {
                    "graphId": result.get("graphId"),
                    "wdkStrategyId": wdk_strategy_id,
                    "wdkUrl": result.get("wdkUrl"),
                    "name": result.get("name"),
                    "description": result.get("description"),
                },
            }
        )

    return events

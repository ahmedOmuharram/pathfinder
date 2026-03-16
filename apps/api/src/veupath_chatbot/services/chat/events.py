"""Semantic chat events and tool-result mapping.

Uses a registry of event extractors so new tool result types can be added
without modifying the dispatcher function (Open/Closed Principle).
"""

from collections.abc import Callable
from typing import Protocol

from veupath_chatbot.domain.strategy.session import StrategyGraph
from veupath_chatbot.platform.types import JSONArray, JSONObject

# ── Event type constants ──────────────────────────────────────────────

GRAPH_SNAPSHOT = "graph_snapshot"
GRAPH_PLAN = "graph_plan"
GRAPH_CLEARED = "graph_cleared"
STRATEGY_LINK = "strategy_link"
STRATEGY_META = "strategy_meta"
STRATEGY_UPDATE = "strategy_update"
PLANNING_ARTIFACT = "planning_artifact"
CITATIONS = "citations"
REASONING = "reasoning"
EXECUTOR_BUILD_REQUEST = "executor_build_request"
WORKBENCH_GENE_SET = "workbench_gene_set"

# ── Type aliases ──────────────────────────────────────────────────────

type GetGraphFn = Callable[[str | None], StrategyGraph | None] | None


class EventExtractor(Protocol):
    """Protocol for event extractor functions."""

    def __call__(
        self, result: JSONObject, *, get_graph: GetGraphFn = None
    ) -> JSONObject | None: ...


# ── Individual extractors ─────────────────────────────────────────────


def _extract_citations(
    result: JSONObject, *, get_graph: GetGraphFn = None
) -> JSONObject | None:
    citations = result.get("citations")
    if isinstance(citations, list) and citations:
        return {"type": CITATIONS, "data": {"citations": citations}}
    return None


def _extract_planning_artifact(
    result: JSONObject, *, get_graph: GetGraphFn = None
) -> JSONObject | None:
    artifact = result.get("planningArtifact")
    if artifact:
        return {"type": PLANNING_ARTIFACT, "data": {"planningArtifact": artifact}}
    return None


def _extract_reasoning(
    result: JSONObject, *, get_graph: GetGraphFn = None
) -> JSONObject | None:
    reasoning = result.get("reasoning")
    if isinstance(reasoning, str) and reasoning.strip():
        return {"type": REASONING, "data": {"reasoning": reasoning}}
    return None


def _extract_conversation_title(
    result: JSONObject, *, get_graph: GetGraphFn = None
) -> JSONObject | None:
    title = result.get("conversationTitle")
    if isinstance(title, str) and title.strip():
        return {"type": STRATEGY_META, "data": {"name": title.strip()}}
    return None


def _extract_executor_build_request(
    result: JSONObject, *, get_graph: GetGraphFn = None
) -> JSONObject | None:
    ebr = result.get("executorBuildRequest")
    if isinstance(ebr, dict):
        return {"type": EXECUTOR_BUILD_REQUEST, "data": {"executorBuildRequest": ebr}}
    return None


def _extract_step_update(
    result: JSONObject, *, get_graph: GetGraphFn = None
) -> JSONObject | None:
    if "stepId" not in result:
        return None
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
    return {
        "type": STRATEGY_UPDATE,
        "data": {"graphId": graph_id, "step": result, "allSteps": all_steps},
    }


def _extract_graph_snapshot(
    result: JSONObject, *, get_graph: GetGraphFn = None
) -> JSONObject | None:
    # Skip extraction when auto-build succeeded — the auto-build hook
    # already emitted a graph_snapshot event with WDK step IDs directly
    # to the event queue. Extracting the tool result's pre-build snapshot
    # here would overwrite it with stale data (isBuilt=false, no wdkStepId).
    auto_build = result.get("autoBuild")
    if isinstance(auto_build, dict) and auto_build.get("ok") is True:
        return None
    snapshot = result.get("graphSnapshot")
    if not snapshot:
        return None
    snapshot_graph_id: str | None = None
    if isinstance(snapshot, dict):
        raw = snapshot.get("graphId")
        snapshot_graph_id = raw if isinstance(raw, str) else None
    if snapshot_graph_id is None:
        raw = result.get("graphId")
        snapshot_graph_id = raw if isinstance(raw, str) else None
    return {
        "type": GRAPH_SNAPSHOT,
        "data": {"graphId": snapshot_graph_id, "graphSnapshot": snapshot},
    }


def _extract_graph_plan(
    result: JSONObject, *, get_graph: GetGraphFn = None
) -> JSONObject | None:
    plan = result.get("plan")
    if not plan:
        return None
    return {
        "type": GRAPH_PLAN,
        "data": {
            "graphId": result.get("graphId"),
            "plan": plan,
            "name": result.get("name"),
            "recordType": result.get("recordType"),
            "description": result.get("description"),
        },
    }


def _extract_strategy_meta(
    result: JSONObject, *, get_graph: GetGraphFn = None
) -> JSONObject | None:
    if not result.get("graphId"):
        return None
    if (
        "name" not in result
        and "description" not in result
        and "recordType" not in result
    ):
        return None
    return {
        "type": STRATEGY_META,
        "data": {
            "graphId": result.get("graphId"),
            "name": result.get("name") or result.get("graphName"),
            "description": result.get("description"),
            "recordType": result.get("recordType"),
            "graphName": result.get("graphName"),
        },
    }


def _extract_cleared(
    result: JSONObject, *, get_graph: GetGraphFn = None
) -> JSONObject | None:
    if result.get("cleared"):
        return {"type": GRAPH_CLEARED, "data": {"graphId": result.get("graphId")}}
    return None


def _extract_gene_set_created(
    result: JSONObject, *, get_graph: GetGraphFn = None
) -> JSONObject | None:
    gene_set = result.get("geneSetCreated")
    if isinstance(gene_set, dict):
        return {"type": WORKBENCH_GENE_SET, "data": {"geneSet": gene_set}}
    return None


def _extract_strategy_link(
    result: JSONObject, *, get_graph: GetGraphFn = None
) -> JSONObject | None:
    wdk_strategy_id = result.get("wdkStrategyId")
    if wdk_strategy_id is None:
        return None
    return {
        "type": STRATEGY_LINK,
        "data": {
            "graphId": result.get("graphId"),
            "wdkStrategyId": wdk_strategy_id,
            "wdkUrl": result.get("wdkUrl"),
            "name": result.get("name"),
            "description": result.get("description"),
            "isSaved": result.get("isSaved"),
        },
    }


# ── Extractor registry ───────────────────────────────────────────────
# Order matters: events are emitted in registration order.

_EXTRACTORS: list[EventExtractor] = [
    _extract_citations,
    _extract_planning_artifact,
    _extract_reasoning,
    _extract_conversation_title,
    _extract_executor_build_request,
    _extract_step_update,
    _extract_graph_snapshot,
    _extract_graph_plan,
    _extract_strategy_meta,
    _extract_cleared,
    _extract_gene_set_created,
    _extract_strategy_link,
]


# ── Public dispatcher ─────────────────────────────────────────────────


def tool_result_to_events(
    result: JSONObject,
    *,
    get_graph: Callable[[str | None], StrategyGraph | None] | None = None,
) -> list[JSONObject]:
    """Convert a tool result dict into a list of semantic chat events.

    Each registered extractor is called in order. Extractors that return
    ``None`` are silently skipped.
    """
    if not isinstance(result, dict):
        return []
    events: list[JSONObject] = []
    for extractor in _EXTRACTORS:
        event = extractor(result, get_graph=get_graph)
        if event is not None:
            events.append(event)
    return events

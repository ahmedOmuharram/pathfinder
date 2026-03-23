"""Semantic chat events and tool-result mapping."""

from collections.abc import Callable
from enum import StrEnum
from typing import Protocol

from veupath_chatbot.domain.strategy.session import StrategyGraph
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.transport.http.schemas.sse import (
    ExecutorBuildRequestEventData,
    GraphClearedEventData,
    GraphPlanEventData,
    ReasoningEventData,
    StrategyLinkEventData,
    StrategyMetaEventData,
    StrategyUpdateEventData,
)
from veupath_chatbot.transport.http.schemas.steps import StepResponse


class EventType(StrEnum):
    """Semantic chat event types emitted during tool-result processing."""

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


type GetGraphFn = Callable[[str | None], StrategyGraph | None] | None


class EventExtractor(Protocol):
    def __call__(
        self, result: JSONObject, *, get_graph: GetGraphFn = None
    ) -> JSONObject | None: ...


def _extract_citations(
    result: JSONObject, *, get_graph: GetGraphFn = None
) -> JSONObject | None:
    citations = result.get("citations")
    if isinstance(citations, list) and citations:
        return {"type": EventType.CITATIONS, "data": {"citations": citations}}
    return None


def _extract_planning_artifact(
    result: JSONObject, *, get_graph: GetGraphFn = None
) -> JSONObject | None:
    artifact = result.get("planningArtifact")
    if artifact:
        return {
            "type": EventType.PLANNING_ARTIFACT,
            "data": {"planningArtifact": artifact},
        }
    return None


def _extract_reasoning(
    result: JSONObject, *, get_graph: GetGraphFn = None
) -> JSONObject | None:
    reasoning = result.get("reasoning")
    if isinstance(reasoning, str) and reasoning.strip():
        return {
            "type": EventType.REASONING,
            "data": ReasoningEventData(reasoning=reasoning).model_dump(
                by_alias=True, exclude_none=True
            ),
        }
    return None


def _extract_conversation_title(
    result: JSONObject, *, get_graph: GetGraphFn = None
) -> JSONObject | None:
    title = result.get("conversationTitle")
    if isinstance(title, str) and title.strip():
        return {
            "type": EventType.STRATEGY_META,
            "data": StrategyMetaEventData(name=title.strip()).model_dump(
                by_alias=True, exclude_none=True
            ),
        }
    return None


def _extract_executor_build_request(
    result: JSONObject, *, get_graph: GetGraphFn = None
) -> JSONObject | None:
    ebr = result.get("executorBuildRequest")
    if isinstance(ebr, dict):
        return {
            "type": EventType.EXECUTOR_BUILD_REQUEST,
            "data": ExecutorBuildRequestEventData(
                executor_build_request=ebr
            ).model_dump(by_alias=True, exclude_none=True),
        }
    return None


def _extract_step_update(
    result: JSONObject, *, get_graph: GetGraphFn = None
) -> JSONObject | None:
    if "stepId" not in result:
        return None
    raw_graph_id = result.get("graphId")
    graph_id = raw_graph_id if isinstance(raw_graph_id, str) else None
    graph = get_graph(graph_id) if get_graph and graph_id else None
    all_steps = (
        [
            StepResponse(
                id=sid,
                kind=s.infer_kind(),
                display_name=s.display_name or s.search_name,
            )
            for sid, s in graph.steps.items()
        ]
        if graph
        else []
    )
    return {
        "type": EventType.STRATEGY_UPDATE,
        "data": StrategyUpdateEventData(
            graph_id=graph_id,
            step=result,
            all_steps=all_steps,
        ).model_dump(by_alias=True, exclude_none=True, mode="json"),
    }


def _extract_graph_snapshot(
    result: JSONObject, *, get_graph: GetGraphFn = None
) -> JSONObject | None:
    auto_build = result.get("autoBuild")
    if isinstance(auto_build, dict) and auto_build.get("ok") is True:
        return None
    snapshot = result.get("graphSnapshot")
    if not snapshot:
        return None
    return {"type": EventType.GRAPH_SNAPSHOT, "data": {"graphSnapshot": snapshot}}


def _extract_graph_plan(
    result: JSONObject, *, get_graph: GetGraphFn = None
) -> JSONObject | None:
    plan = result.get("plan")
    if not isinstance(plan, dict):
        return None
    return {
        "type": EventType.GRAPH_PLAN,
        "data": GraphPlanEventData.model_validate(result).model_dump(
            by_alias=True, exclude_none=True
        ),
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
        "type": EventType.STRATEGY_META,
        "data": StrategyMetaEventData.model_validate(result).model_dump(
            by_alias=True, exclude_none=True
        ),
    }


def _extract_cleared(
    result: JSONObject, *, get_graph: GetGraphFn = None
) -> JSONObject | None:
    if result.get("cleared"):
        return {
            "type": EventType.GRAPH_CLEARED,
            "data": GraphClearedEventData.model_validate(result).model_dump(
                by_alias=True
            ),
        }
    return None


def _extract_gene_set_created(
    result: JSONObject, *, get_graph: GetGraphFn = None
) -> JSONObject | None:
    gene_set = result.get("geneSetCreated")
    if isinstance(gene_set, dict):
        return {"type": EventType.WORKBENCH_GENE_SET, "data": {"geneSet": gene_set}}
    return None


def _extract_strategy_link(
    result: JSONObject, *, get_graph: GetGraphFn = None
) -> JSONObject | None:
    if result.get("wdkStrategyId") is None:
        return None
    return {
        "type": EventType.STRATEGY_LINK,
        "data": StrategyLinkEventData.model_validate(result).model_dump(
            by_alias=True, exclude_none=True
        ),
    }


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


def tool_result_to_events(
    result: JSONObject,
    *,
    get_graph: Callable[[str | None], StrategyGraph | None] | None = None,
) -> list[JSONObject]:
    """Convert a tool result dict into a list of semantic chat events."""
    if not isinstance(result, dict):
        return []
    events: list[JSONObject] = []
    for extractor in _EXTRACTORS:
        event = extractor(result, get_graph=get_graph)
        if event is not None:
            events.append(event)
    return events

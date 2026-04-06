"""Pydantic-ai lifecycle hooks for the PathFinder agents.

Three hooks are registered:

1. **Discovery tracking** — after ``get_search_overview``, parse the result
   and register the search in ``AgentToolState``.
2. **Auto-build** — after any graph-mutating tool, push to WDK, sync the
   strategy, create/update the gene set, and emit SSE events.
3. **Result slimming** — after graph-mutating tools, replace the verbose
   ``StepOkResponse`` JSON with a compact one-liner (the model sees the
   full graph via the pinned dynamic instruction).
"""

from __future__ import annotations

import contextlib
import json
from typing import Any, cast

from pydantic import ConfigDict, Field, ValidationError
from pydantic_ai.capabilities.hooks import Hooks
from pydantic_ai.messages import ToolCallPart
from pydantic_ai.tools import RunContext, ToolDefinition

from veupath_chatbot.ai.agents.state import SearchOverview
from veupath_chatbot.ai.context.rendering import render_slim_step_result
from veupath_chatbot.ai.orchestration.deps import AgentDeps
from veupath_chatbot.ai.tools.standalone._graph_helpers import build_graph_snapshot
from veupath_chatbot.domain.strategy.session import StrategyGraph
from veupath_chatbot.platform.errors import AppError, sanitize_error_for_client
from veupath_chatbot.platform.event_schemas import (
    GraphSnapshotEventData,
    StrategyLinkEventData,
)
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.parsing import parse_jsonish
from veupath_chatbot.platform.pydantic_base import CamelModel
from veupath_chatbot.platform.types import JSONArray, JSONObject
from veupath_chatbot.services.gene_sets import GeneSetService
from veupath_chatbot.services.gene_sets.store import get_gene_set_store
from veupath_chatbot.services.gene_sets.wdk_helpers import GeneSetWdkContext
from veupath_chatbot.services.strategies.build import RootResolutionError
from veupath_chatbot.services.strategies.schemas import StepResponse
from veupath_chatbot.services.strategies.step_wdk_push import push_all_steps_to_wdk
from veupath_chatbot.services.strategies.sync import SyncResult, sync_strategy_for_site

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Internal models
# ---------------------------------------------------------------------------

_GRAPH_MUTATING_TOOLS: frozenset[str] = frozenset(
    {
        "create_leaf_step",
        "combine_steps",
        "transform_step",
        "update_step",
        "delete_step",
        "undo_last_change",
        "add_step_filter",
        "add_step_analysis",
        "add_step_report",
    }
)


class _RawSearchOverview(CamelModel):
    """Lenient parser for search overview tool results."""

    model_config = ConfigDict(extra="ignore")

    searchName: str = ""
    displayName: str = ""
    recordType: str = ""
    description: str = ""
    required: list[JSONObject] = Field(default_factory=list)
    optional: list[JSONObject] = Field(default_factory=list)


class _SlimParseResponse(CamelModel):
    """Lenient parser for StepOkResponse — ignores extra keys like autoBuild."""

    model_config = ConfigDict(extra="ignore")

    ok: bool = True
    step: StepResponse = Field(...)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _merge_auto_build(original_text: str, extra: JSONObject) -> str:
    """Merge auto-build data into the tool result as valid JSON."""
    parsed: JSONObject = {}
    if original_text:
        with contextlib.suppress(ValidationError, ValueError):
            parsed = json.loads(original_text)
    parsed.update(extra)
    return json.dumps(parsed)


def _build_graph_snapshot_for_event(
    deps: AgentDeps,
    graph: StrategyGraph,
) -> GraphSnapshotEventData:
    """Build a ``GraphSnapshotEventData`` from the graph.

    Uses the standalone ``build_graph_snapshot`` helper (no mixin chain).
    """
    content = build_graph_snapshot(deps.strategy_session, graph)
    return GraphSnapshotEventData(graph_snapshot=content)


# ---------------------------------------------------------------------------
# Discovery tracking
# ---------------------------------------------------------------------------


def _track_search_discovery(deps: AgentDeps, result_text: str) -> None:
    """Extract search overview from tool result and register in agent state."""
    parsed = parse_jsonish(result_text)
    if not parsed or not isinstance(parsed, dict):
        return

    try:
        raw = _RawSearchOverview.model_validate(parsed)
    except ValidationError:
        return
    if not raw.searchName:
        return

    required_names = [str(p.get("name", "")) for p in raw.required]
    all_params = list(required_names)
    all_params.extend(str(p.get("name", "")) for p in raw.optional)

    overview = SearchOverview(
        search_name=raw.searchName,
        display_name=raw.displayName or raw.searchName,
        record_type=raw.recordType or "transcript",
        description=raw.description,
        parameter_names=all_params,
        required_params=required_names,
    )
    deps.agent_state.register_search(raw.searchName, overview)


# ---------------------------------------------------------------------------
# Auto-build
# ---------------------------------------------------------------------------


async def _auto_build(deps: AgentDeps, graph: StrategyGraph) -> JSONObject:
    """Push to WDK, sync strategy, create gene set, emit events.

    Returns the ``autoBuild`` payload to merge into the tool result.
    """
    await push_all_steps_to_wdk(graph, deps.site_id, update_existing=True)

    sync_result = await sync_strategy_for_site(
        graph=graph,
        site_id=deps.site_id,
        strategy_name=graph.name,
    )

    build_data: JSONObject = {
        "ok": True,
        "wdkStrategyId": sync_result.wdk_strategy_id,
        "wdkUrl": sync_result.wdk_url,
        "counts": {str(k): v for k, v in sync_result.counts.items()},
        "rootCount": sync_result.root_count,
        "zeroStepIds": cast("JSONArray", sync_result.zero_step_ids),
    }

    await _maybe_create_gene_set(deps, sync_result, build_data, graph)
    _emit_strategy_link(deps, sync_result, graph)
    _emit_graph_snapshot(deps, graph)

    return build_data


async def _maybe_create_gene_set(
    deps: AgentDeps,
    sync_result: SyncResult,
    build_data: JSONObject,
    graph: StrategyGraph,
) -> None:
    """Create or reuse the gene set for the strategy."""
    if sync_result.wdk_strategy_id is None or deps.user_id is None:
        return
    try:
        store = get_gene_set_store()
        svc = GeneSetService(store)

        # Attempt to find an existing gene set for this strategy.
        gs = svc.find_by_wdk_strategy(deps.user_id, sync_result.wdk_strategy_id)

        if gs is not None:
            gs.wdk_strategy_id = sync_result.wdk_strategy_id
            gs.name = graph.name or gs.name
            store.save(gs)
            await svc.flush(gs.id)
        else:
            gs = await svc.create(
                user_id=deps.user_id,
                name=graph.name or "Strategy gene set",
                site_id=deps.site_id,
                gene_ids=[],
                source="strategy",
                wdk=GeneSetWdkContext(
                    wdk_strategy_id=sync_result.wdk_strategy_id,
                    record_type=graph.record_type,
                ),
            )
            await svc.flush(gs.id)

        build_data["geneSetCreated"] = {
            "id": gs.id,
            "name": gs.name,
            "geneCount": len(gs.gene_ids),
            "source": gs.source,
            "siteId": gs.site_id,
        }
    except (AppError, OSError) as gs_exc:
        logger.warning("Gene set creation failed", error=str(gs_exc))


def _emit_strategy_link(
    deps: AgentDeps, sync_result: SyncResult, graph: StrategyGraph
) -> None:
    """Emit strategy_link so frontend updates immediately."""
    deps.emit_event(
        {
            "type": "strategy_link",
            "data": StrategyLinkEventData(
                graph_id=graph.id,
                wdk_strategy_id=sync_result.wdk_strategy_id,
                wdk_url=sync_result.wdk_url,
                name=graph.name,
                is_saved=False,
            ).model_dump(by_alias=True, exclude_none=True),
        }
    )


def _emit_graph_snapshot(deps: AgentDeps, graph: StrategyGraph) -> None:
    """Emit graph_snapshot with updated WDK step IDs and counts."""
    snapshot_data = _build_graph_snapshot_for_event(deps, graph)
    deps.emit_event(
        {
            "type": "graph_snapshot",
            "data": snapshot_data.model_dump(by_alias=True, exclude_none=True),
        }
    )


def _slim_graph_result(result_text: str, graph: StrategyGraph) -> str | None:
    """Replace full StepOkResponse JSON with a one-liner.

    Returns the slim text, or ``None`` if slimming was not possible.
    """
    try:
        response = _SlimParseResponse.model_validate_json(result_text)
    except (ValidationError, ValueError):
        logger.debug("Slim parse failed, len=%d", len(result_text))
        return None

    if not response.ok:
        return None

    step = response.step
    input_ids = None
    if step.primary_input_step_id and step.secondary_input_step_id:
        input_ids = (step.primary_input_step_id, step.secondary_input_step_id)

    return render_slim_step_result(
        step_id=step.id,
        search_name=step.search_name or "",
        display_name=step.display_name,
        estimated_size=graph.step_counts.get(step.id),
        operator=step.operator,
        input_ids=input_ids,
    )


# ---------------------------------------------------------------------------
# Hook registration
# ---------------------------------------------------------------------------

executor_hooks: Hooks[AgentDeps] = Hooks()


@executor_hooks.on.after_tool_execute(tools=["get_search_overview"])
async def discovery_tracking_hook(
    ctx: RunContext[AgentDeps],
    /,
    *,
    call: ToolCallPart,
    tool_def: ToolDefinition,
    args: Any,
    result: Any,
) -> Any:
    """Track discovered searches in agent state after get_search_overview."""
    if isinstance(result, str):
        _track_search_discovery(ctx.deps, result)
    return result


@executor_hooks.on.after_tool_execute(tools=list(_GRAPH_MUTATING_TOOLS))
async def auto_build_and_slim_hook(
    ctx: RunContext[AgentDeps],
    /,
    *,
    call: ToolCallPart,
    tool_def: ToolDefinition,
    args: Any,
    result: Any,
) -> Any:
    """After graph-mutating tools: auto-build if single root, slim the result."""
    deps = ctx.deps
    graph = deps.strategy_session.get_graph(None)
    if not graph:
        return result

    result_text = result if isinstance(result, str) else str(result)

    if len(graph.roots) == 1:
        try:
            build_data = await _auto_build(deps, graph)
            result_text = _merge_auto_build(
                result_text, {"autoBuild": build_data}
            )
        except (AppError, OSError, RootResolutionError) as exc:
            error_payload: JSONObject = {
                "ok": False,
                "error": sanitize_error_for_client(exc),
            }
            unpushed: list[JSONObject] = []
            for sid, step in graph.steps.items():
                if sid not in graph.wdk_step_ids:
                    entry: JSONObject = {
                        "stepId": sid,
                        "searchName": step.search_name,
                    }
                    push_error = graph.wdk_push_errors.get(sid)
                    if push_error:
                        entry["pushError"] = push_error
                    unpushed.append(entry)
            if unpushed:
                error_payload["unpushedSteps"] = cast("JSONArray", unpushed)
                error_payload["hint"] = (
                    "These steps were created locally but WDK rejected them. "
                    "Fix their parameters with update_step, or delete them "
                    "with delete_step."
                )
            result_text = _merge_auto_build(
                result_text, {"autoBuild": error_payload}
            )
            logger.warning("Auto-build failed", error=str(exc))

    elif len(graph.roots) > 1:
        root_names = [
            graph.steps[r].display_name or graph.steps[r].search_name
            for r in sorted(graph.roots)
            if r in graph.steps
        ]
        note = (
            f"\n\nNote: Graph has {len(graph.roots)} disconnected roots: "
            f"{root_names}. Call combine_steps to connect them before "
            f"the strategy can be built."
        )
        result_text = result_text + note

    # Slim the result — the model sees graph state via dynamic instructions.
    slim = _slim_graph_result(result_text, graph)
    if slim is not None:
        return slim

    return result_text

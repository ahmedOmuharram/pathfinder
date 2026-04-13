"""Post-tool-execution hooks for PathFinder agents.

Three hooks are applied after tool execution:

1. **Discovery tracking** — after ``get_search_overview``, parse the result
   and register the search in ``AgentToolState``.
2. **Auto-build** — after any graph-mutating tool, push to WDK, sync the
   strategy, create/update the gene set, and emit SSE events.
3. **Result slimming** — after graph-mutating tools, replace the verbose
   ``StepOkResponse`` JSON with a compact one-liner (the model sees the
   full graph via the pinned dynamic instruction).

These are plain async functions applied via PydanticAI's native ``Hooks``
capability (``after_tool_execute``).
"""

from __future__ import annotations

import contextlib
import json
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic_ai.messages import ToolCallPart, ToolReturn
from pydantic_ai.tools import RunContext, ToolDefinition
from pydantic_ai.ui.vercel_ai.response_types import DataChunk

from pathfinder.ai.agents.state import SearchOverview
from pathfinder.ai.context.rendering import render_slim_step_result
from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.ai.tools.standalone._stream_parts import (
    graph_snapshot_chunk,
    strategy_link_chunk,
)
from pathfinder.domain.strategy.session import StrategyGraph
from pathfinder.domain.strategy.types import SyncStateProtocol
from pathfinder.platform.errors import AppError, sanitize_error_for_client
from pathfinder.platform.logging import get_logger
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.platform.types import JSONArray, JSONObject
from pathfinder.services.gene_sets import GeneSetService
from pathfinder.services.gene_sets.store import get_gene_set_store
from pathfinder.services.gene_sets.wdk_helpers import GeneSetWdkContext
from pathfinder.services.strategies.build import RootResolutionError
from pathfinder.services.strategies.schemas import StepResponse
from pathfinder.services.strategies.step_wdk_push import push_all_steps_to_wdk
from pathfinder.services.strategies.sync import SyncResult, sync_strategy_for_site
from pathfinder.services.strategies.sync_state import ensure_sync_state

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


class _ParamEntry(CamelModel):
    """One parameter entry inside a search overview result."""

    model_config = ConfigDict(extra="ignore")

    name: str = ""


class _RawSearchOverview(CamelModel):
    """Lenient parser for search overview tool results."""

    model_config = ConfigDict(extra="ignore")

    searchName: str = ""
    displayName: str = ""
    recordType: str = ""
    description: str = ""
    required: list[_ParamEntry] = Field(default_factory=list)
    optional: list[_ParamEntry] = Field(default_factory=list)


class _SlimParseResponse(CamelModel):
    """Lenient parser for StepOkResponse — ignores extra keys like autoBuild."""

    model_config = ConfigDict(extra="ignore")

    ok: bool = True
    step: StepResponse = Field(...)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _ErrorFlag(CamelModel):
    """Minimal model to detect error payloads without manual parsing."""

    model_config = ConfigDict(extra="ignore")

    ok: bool = True


def _is_error_result(text: str) -> bool:
    """Check whether a tool result is an error that should skip auto-build."""
    if text.startswith("ERROR:"):
        return True
    with contextlib.suppress(ValidationError, ValueError):
        return not _ErrorFlag.model_validate_json(text).ok
    return False


def _merge_auto_build(original_text: str, extra: JSONObject) -> str:
    """Merge auto-build data into the tool result as valid JSON."""
    parsed: JSONObject = {}
    if original_text:
        with contextlib.suppress(ValidationError, ValueError):
            parsed = json.loads(original_text)
    parsed.update(extra)
    return json.dumps(parsed)


# ---------------------------------------------------------------------------
# Discovery tracking
# ---------------------------------------------------------------------------


def _track_search_discovery(deps: AgentDeps, result_text: str) -> None:
    """Extract search overview from tool result and register in agent state."""
    try:
        raw = _RawSearchOverview.model_validate_json(result_text)
    except (ValidationError, ValueError):
        return
    if not raw.searchName:
        return

    required_names = [p.name for p in raw.required]
    all_params = list(required_names)
    all_params.extend(p.name for p in raw.optional)

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


async def _auto_build(
    deps: AgentDeps, graph: StrategyGraph
) -> tuple[JSONObject, list[DataChunk]]:
    """Push to WDK, sync strategy, create gene set, build data-part chunks.

    Returns a pair of ``(build_data, chunks)`` where ``build_data`` is the
    ``autoBuild`` payload to merge into the tool result and ``chunks`` are
    the ``DataChunk`` entries to append to ``ToolReturn.metadata`` for the
    SSE stream.
    """
    sync_state = ensure_sync_state(deps.strategy_session)
    await push_all_steps_to_wdk(graph, sync_state, deps.site_id, update_existing=True)

    sync_result = await sync_strategy_for_site(
        graph=graph,
        sync_state=sync_state,
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

    # Build data-part chunks replacing the old strategy_link + graph_snapshot
    # SSE events. The wdk_strategy_id is an int returned by WDK, not a
    # PathFinder graph id; we keep the stream-part strategyId consistent with
    # graph.id (used by the UI graph store keyed by graph id).
    chunks: list[DataChunk] = []
    if sync_result.wdk_url is not None:
        chunks.append(
            strategy_link_chunk(
                strategy_id=graph.id,
                url=sync_result.wdk_url,
                title=graph.name,
            )
        )
    chunks.append(graph_snapshot_chunk(deps.strategy_session, graph))

    return build_data, chunks


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


def _slim_graph_result(
    result_text: str, graph: StrategyGraph, sync_state: SyncStateProtocol | None
) -> str | None:
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

    estimated_size = sync_state.step_counts.get(step.id) if sync_state else None
    return render_slim_step_result(
        step_id=step.id,
        search_name=step.search_name or "",
        display_name=step.display_name,
        estimated_size=estimated_size,
        operator=step.operator,
        input_ids=input_ids,
    )


# ---------------------------------------------------------------------------
# Public hook entry points (used as after_tool_execute in Hooks capability)
# ---------------------------------------------------------------------------


async def apply_discovery_hook(
    ctx: RunContext[AgentDeps],
    /,
    *,
    call: ToolCallPart,
    tool_def: ToolDefinition,
    args: dict[str, Any],
    result: Any,
) -> Any:
    """Apply discovery-tracking post-tool logic for get_search_overview."""
    if call.tool_name != "get_search_overview":
        return result
    if isinstance(result, str):
        _track_search_discovery(ctx.deps, result)
    return result


def _build_auto_build_error_payload(
    exc: AppError | OSError | RootResolutionError,
    graph: StrategyGraph,
    sync_state: SyncStateProtocol | None,
) -> JSONObject:
    """Build the autoBuild error payload for a failed auto-build."""
    error_payload: JSONObject = {
        "ok": False,
        "error": sanitize_error_for_client(exc),
    }
    unpushed: list[JSONObject] = []
    wdk_step_ids = sync_state.wdk_step_ids if sync_state else {}
    wdk_push_errors = sync_state.wdk_push_errors if sync_state else {}
    for sid, step in graph.steps.items():
        if sid not in wdk_step_ids:
            entry: JSONObject = {
                "stepId": sid,
                "searchName": step.search_name,
            }
            push_error = wdk_push_errors.get(sid)
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
    return error_payload


async def _apply_single_root_build(
    deps: AgentDeps, graph: StrategyGraph, result_text: str
) -> tuple[str, list[DataChunk]]:
    """Run auto-build for a single-root graph and merge the result.

    Returns ``(updated_result_text, chunks)`` where ``chunks`` are new
    ``DataChunk`` entries to append to ``ToolReturn.metadata``.
    """
    try:
        build_data, chunks = await _auto_build(deps, graph)
        return _merge_auto_build(result_text, {"autoBuild": build_data}), chunks
    except (AppError, OSError, RootResolutionError) as exc:
        error_payload = _build_auto_build_error_payload(exc, graph, deps.strategy_session.sync_state)
        logger.warning("Auto-build failed", error=str(exc))
        return _merge_auto_build(result_text, {"autoBuild": error_payload}), []


def _serialize_tool_return_value(raw_value: Any) -> str:
    """Stringify a tool's return_value to JSON-ish text for result slimming.

    Mirrors ``serialize_tool_content`` in
    :mod:`pathfinder.services.chat.streaming.events` — kept local to avoid
    pulling a services-layer import into the AI agents layer. Pydantic
    ``BaseModel`` instances dump via ``model_dump(by_alias=True, mode="json")``.
    """
    if isinstance(raw_value, str):
        return raw_value
    if isinstance(raw_value, BaseModel):
        return json.dumps(raw_value.model_dump(by_alias=True, mode="json"))
    if isinstance(raw_value, (dict, list)):
        try:
            return json.dumps(raw_value)
        except (TypeError, ValueError):
            return str(raw_value)
    return str(raw_value)


def _extract_text_and_metadata(result: Any) -> tuple[str, list[DataChunk]]:
    """Split an incoming tool result into (text, existing metadata chunks).

    Tools that return ``ToolReturn`` contribute a typed ``return_value`` and
    a list of already-built ``metadata`` chunks. Older tools that return a
    plain string or dict contribute just the serialized text and no chunks.
    """
    if isinstance(result, ToolReturn):
        text = _serialize_tool_return_value(result.return_value)
        existing_metadata = result.metadata
        chunks: list[DataChunk] = []
        if isinstance(existing_metadata, list):
            chunks = [c for c in existing_metadata if isinstance(c, DataChunk)]
        return text, chunks
    text = result if isinstance(result, str) else str(result)
    return text, []


async def apply_auto_build_hook(
    ctx: RunContext[AgentDeps],
    /,
    *,
    call: ToolCallPart,
    tool_def: ToolDefinition,
    args: dict[str, Any],
    result: Any,
) -> Any:
    """Apply auto-build and result-slimming for graph-mutating tools.

    Preserves any existing ``ToolReturn.metadata`` chunks emitted by the
    tool and appends auto-build chunks (``data-strategy-link`` and a
    refreshed ``data-graph-snapshot``).
    """
    if call.tool_name not in _GRAPH_MUTATING_TOOLS:
        return result

    deps = ctx.deps
    graph = deps.strategy_session.get_graph(None)
    if not graph:
        return result

    result_text, existing_chunks = _extract_text_and_metadata(result)

    if _is_error_result(result_text):
        return result_text

    auto_build_chunks: list[DataChunk] = []
    if len(graph.roots) == 1:
        result_text, auto_build_chunks = await _apply_single_root_build(
            deps, graph, result_text
        )
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
    slim = _slim_graph_result(result_text, graph, deps.strategy_session.sync_state)
    final_text = slim if slim is not None else result_text

    # Merge pre-existing chunks with auto-build chunks. Replace the
    # tool's own `data-graph-snapshot` with the post-build refreshed one
    # (the pre-build snapshot lacked wdkStrategyId / updated counts).
    chunks = [
        c for c in existing_chunks if c.type != "data-graph-snapshot"
    ]
    chunks.extend(auto_build_chunks)

    return ToolReturn(return_value=final_text, metadata=chunks)


__all__ = [
    "apply_auto_build_hook",
    "apply_discovery_hook",
]

"""Kani agent runtime (class + subkani orchestration)."""

import asyncio
import contextlib
import json
from dataclasses import dataclass, field
from typing import Annotated, cast
from uuid import UUID

from kani import AIParam, ChatMessage, Kani, ai_function
from kani.ai_function import AIFunction
from kani.engines.base import BaseEngine
from kani.internal import FunctionCallResult
from kani.models import FunctionCall
from pydantic import TypeAdapter, ValidationError

from veupath_chatbot.ai.agents.engine_factory import create_engine
from veupath_chatbot.ai.engines.mock import MockEngine
from veupath_chatbot.ai.models.catalog import get_model_entry
from veupath_chatbot.ai.orchestration.subkani.orchestrator import (
    delegate_strategy_subtasks as subkani_delegate_strategy_subtasks,
)
from veupath_chatbot.ai.orchestration.types import SubkaniContext
from veupath_chatbot.ai.prompts.executor_prompt import build_agent_system_prompt
from veupath_chatbot.ai.tools.catalog_tools import CatalogTools
from veupath_chatbot.ai.tools.conversation_tools import ConversationTools
from veupath_chatbot.ai.tools.execution_tools import ExecutionTools
from veupath_chatbot.ai.tools.result_tools import ResultTools
from veupath_chatbot.ai.tools.strategy_tools import StrategyTools
from veupath_chatbot.ai.tools.unified_registry import UnifiedToolRegistryMixin
from veupath_chatbot.domain.strategy.session import StrategyGraph
from veupath_chatbot.platform.errors import AppError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONArray, JSONObject
from veupath_chatbot.services.gene_sets import GeneSetService
from veupath_chatbot.services.gene_sets.operations import GeneSetWdkContext
from veupath_chatbot.services.gene_sets.store import get_gene_set_store
from veupath_chatbot.services.research import (
    LiteratureSearchService,
    WebSearchService,
)
from veupath_chatbot.services.strategies.build import RootResolutionError
from veupath_chatbot.services.strategies.session_factory import build_strategy_session
from veupath_chatbot.services.strategies.sync import (
    SyncResult,
    sync_strategy_for_site,
)
from veupath_chatbot.transport.http.schemas.sse import (
    GraphSnapshotContent,
    GraphSnapshotEventData,
    StrategyLinkEventData,
)

logger = get_logger(__name__)


@dataclass
class AgentContext:
    """Context for building a PathfinderAgent."""

    site_id: str
    user_id: UUID | None = None
    chat_history: list[ChatMessage] = field(default_factory=list)
    strategy_graph: JSONObject | None = None
    selected_nodes: JSONObject | None = None
    mentioned_context: str | None = None
    disable_rag: bool = False
    desired_response_tokens: int | None = None


_DICT_ADAPTER: TypeAdapter[JSONObject] = TypeAdapter(JSONObject)


def _merge_auto_build(original_text: str | None, extra: JSONObject) -> str:
    """Merge auto-build data into the tool result as valid JSON.

    Keeps the original tool result fields intact and adds/overwrites keys
    from ``extra``.  If the original text isn't parseable JSON, wraps
    ``extra`` in a standalone JSON string.
    """
    parsed: JSONObject = {}
    if original_text:
        with contextlib.suppress(ValidationError):
            parsed = _DICT_ADAPTER.validate_json(original_text)
    parsed.update(extra)
    return json.dumps(parsed)


class PathfinderAgent(UnifiedToolRegistryMixin, Kani):
    """Unified VEuPathDB Strategy Agent - research, planning, and execution.

    Combines executor (graph building, delegation, WDK execution) and
    planner (gene lookup, control tests, parameter optimization, artifacts)
    capabilities in a single agent. The model decides per-turn whether to
    research/plan or build/execute.
    """

    functions: dict[str, AIFunction]

    def __init__(self, engine: BaseEngine, context: AgentContext) -> None:
        site_id = context.site_id
        self.site_id = site_id
        self.user_id = context.user_id
        self.strategy_session = build_strategy_session(
            site_id=site_id, strategy_graph=context.strategy_graph
        )

        self.catalog_tools = CatalogTools(site_id)
        self.strategy_tools = StrategyTools(self.strategy_session)
        self.execution_tools = ExecutionTools(self.strategy_session)
        self.result_tools = ResultTools(self.strategy_session)
        self.conversation_tools = ConversationTools(
            self.strategy_session, context.user_id
        )
        self.web_search_service = WebSearchService()
        self.literature_search_service = LiteratureSearchService()

        system_prompt = build_agent_system_prompt(
            site_id=site_id,
            selected_nodes=context.selected_nodes,
            mentioned_context=context.mentioned_context,
        )

        super().__init__(
            engine=engine,
            system_prompt=system_prompt,
            chat_history=context.chat_history,
            desired_response_tokens=context.desired_response_tokens,
        )
        self.event_queue: asyncio.Queue[JSONObject] | None = None
        # Cancellation signal - set by stream_chat when the client disconnects.
        # Required by OptimizationToolsMixin for long-running optimization runs.
        self._cancel_event = asyncio.Event()
        # Track the gene set created by auto-build so rebuilds reuse it.
        self._auto_build_gene_set_id: str | None = None

    async def _emit_event(self, event: JSONObject) -> None:
        if self.event_queue is not None:
            await self.event_queue.put(event)

    # -- Auto-build hook -------------------------------------------------------
    _GRAPH_MUTATING_TOOLS = frozenset(
        {
            "create_step",
            "delegate_strategy_subtasks",
            "update_step",
            "delete_step",
            "undo_last_change",
            "ensure_single_output",
            "rename_step",
            "add_step_filter",
            "add_step_analysis",
            "add_step_report",
        }
    )

    async def do_function_call(
        self, call: FunctionCall, tool_call_id: str | None = None
    ) -> FunctionCallResult:
        """Execute a tool call, then auto-build if the graph is ready.

        After any graph-mutating tool, if the graph has exactly one root
        and hasn't been pushed to WDK yet, build it. The result (or error)
        is appended to the tool's return message so the model sees it.
        """
        result = await super().do_function_call(call, tool_call_id)

        if call.name not in self._GRAPH_MUTATING_TOOLS:
            return result

        graph = self.strategy_session.get_graph(None)
        if not graph:
            return result

        return (
            self._handle_multi_root(result, graph)
            if len(graph.roots) != 1
            else await self._auto_build(result, graph)
        )

    def _handle_multi_root(
        self, result: FunctionCallResult, graph: object
    ) -> FunctionCallResult:
        """Attach skip data when graph has multiple roots."""
        if not isinstance(graph, StrategyGraph):
            return result
        skip_data: JSONObject = {
            "autoBuild": {
                "ok": False,
                "skipped": True,
                "reason": "multiple_roots",
                "rootCount": len(graph.roots),
            },
        }
        if graph.wdk_step_ids:
            auto_build_dict = cast("JSONObject", skip_data["autoBuild"])
            auto_build_dict["existingWdkStepIds"] = dict(graph.wdk_step_ids)
        result.message.content = _merge_auto_build(result.message.text, skip_data)
        return result

    async def _auto_build(
        self, result: FunctionCallResult, graph: object
    ) -> FunctionCallResult:
        """Build the strategy and attach build data to the result."""
        if not isinstance(graph, StrategyGraph):
            return result
        try:
            sync_result = await sync_strategy_for_site(
                graph=graph,
                site_id=self.site_id,
                strategy_name=graph.name,
            )

            build_data: JSONObject = {
                "autoBuild": {
                    "ok": True,
                    "wdkStrategyId": sync_result.wdk_strategy_id,
                    "wdkUrl": sync_result.wdk_url,
                    "counts": {str(k): v for k, v in sync_result.counts.items()},
                    "rootCount": sync_result.root_count,
                    "zeroStepIds": cast("JSONArray", sync_result.zero_step_ids),
                },
            }

            await self._maybe_create_gene_set(sync_result, build_data, graph)
            await self._emit_strategy_link(sync_result, graph)
            await self._emit_graph_snapshot(graph)

            result.message.content = _merge_auto_build(result.message.text, build_data)

        except (AppError, OSError, RootResolutionError) as exc:
            result.message.content = _merge_auto_build(
                result.message.text,
                {"autoBuild": {"ok": False, "error": str(exc)}},
            )
            logger.warning("Auto-build failed", error=str(exc))

        return result

    async def _maybe_create_gene_set(
        self, sync_result: SyncResult, build_data: JSONObject, graph: StrategyGraph
    ) -> None:
        """Create or reuse the gene set for the strategy."""
        if sync_result.wdk_strategy_id is None or self.user_id is None:
            return
        try:
            store = get_gene_set_store()
            svc = GeneSetService(store)

            gs = None
            if self._auto_build_gene_set_id:
                gs = store.get(self._auto_build_gene_set_id)
            if gs is None:
                gs = svc.find_by_wdk_strategy(
                    self.user_id, sync_result.wdk_strategy_id
                )

            if gs is not None:
                gs.wdk_strategy_id = sync_result.wdk_strategy_id
                gs.name = graph.name or gs.name
                store.save(gs)
                await svc.flush(gs.id)
            else:
                gs = await svc.create(
                    user_id=self.user_id,
                    name=graph.name or "Strategy gene set",
                    site_id=self.site_id,
                    gene_ids=[],
                    source="strategy",
                    wdk=GeneSetWdkContext(
                        wdk_strategy_id=sync_result.wdk_strategy_id,
                        record_type=graph.record_type,
                    ),
                )
                await svc.flush(gs.id)

            self._auto_build_gene_set_id = gs.id
            ab = cast("JSONObject", build_data["autoBuild"])
            ab["geneSetCreated"] = {
                "id": gs.id,
                "name": gs.name,
                "geneCount": len(gs.gene_ids),
                "source": gs.source,
                "siteId": gs.site_id,
            }
        except (AppError, OSError) as gs_exc:
            logger.warning("Gene set creation failed", error=str(gs_exc))

    async def _emit_strategy_link(
        self, sync_result: SyncResult, graph: StrategyGraph
    ) -> None:
        """Emit strategy_link so frontend updates immediately."""
        await self._emit_event(
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

    async def _emit_graph_snapshot(self, graph: StrategyGraph) -> None:
        """Emit graph_snapshot with updated WDK step IDs and counts."""
        await self._emit_event(
            {
                "type": "graph_snapshot",
                "data": GraphSnapshotEventData(
                    graph_snapshot=GraphSnapshotContent.model_validate(
                        self.strategy_tools._build_graph_snapshot(graph)
                    ),
                ).model_dump(by_alias=True, exclude_none=True),
            }
        )

    @ai_function()
    async def delegate_strategy_subtasks(
        self,
        goal: Annotated[str, AIParam(desc="Overall user goal for the strategy")],
        plan: Annotated[
            JSONObject | None,
            AIParam(
                desc=(
                    "Nested delegation plan tree (binary combine nodes + task nodes). "
                    "Do not include any top-level keys besides 'goal' and 'plan'. "
                    "Combine nodes must include both 'left' and 'right'."
                )
            ),
        ] = None,
    ) -> JSONObject:
        """Spawn sub-kanis to discover searches and parameters (nested plan)."""
        if isinstance(self.engine, MockEngine):

            def _engine_factory() -> BaseEngine:
                return MockEngine(site_id=self.site_id)

        else:
            parent_entry = get_model_entry(getattr(self.engine, "model", ""))
            parent_provider = parent_entry.provider if parent_entry else None

            def _engine_factory() -> BaseEngine:
                return create_engine(
                    provider_override=parent_provider,
                    model_override=_SUBKANI_MODEL_BY_PROVIDER.get(
                        parent_provider or ""
                    ),
                )

        return await subkani_delegate_strategy_subtasks(
            goal=goal,
            context=SubkaniContext(
                site_id=self.site_id,
                strategy_session=self.strategy_session,
                chat_history=self.chat_history,
                emit_event=self._emit_event,
                subkani_timeout_seconds=0,
                engine_factory=_engine_factory,
            ),
            strategy_tools=self.strategy_tools,
            plan=plan,
        )


# Cheapest model per provider for sub-kani delegation.
_SUBKANI_MODEL_BY_PROVIDER: dict[str, str | None] = {
    "openai": None,  # None = use settings.subkani_model (gpt-4.1-mini)
    "anthropic": "anthropic/claude-haiku-4-5",
    "google": "google/gemini-2.5-pro",
    "ollama": None,
}

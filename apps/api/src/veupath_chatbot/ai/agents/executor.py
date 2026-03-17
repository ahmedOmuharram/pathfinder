"""Kani agent runtime (class + subkani orchestration)."""

import asyncio
import json
from typing import Annotated, cast
from uuid import UUID

from kani import AIParam, ChatMessage, Kani, ai_function
from kani.ai_function import AIFunction
from kani.engines.base import BaseEngine
from kani.internal import FunctionCallResult
from kani.models import FunctionCall

from veupath_chatbot.ai.orchestration.subkani.orchestrator import (
    delegate_strategy_subtasks as subkani_delegate_strategy_subtasks,
)
from veupath_chatbot.ai.prompts.executor_prompt import build_agent_system_prompt
from veupath_chatbot.ai.tools.catalog_rag_tools import CatalogRagTools
from veupath_chatbot.ai.tools.catalog_tools import CatalogTools
from veupath_chatbot.ai.tools.conversation_tools import ConversationTools
from veupath_chatbot.ai.tools.example_plans_rag_tools import ExamplePlansRagTools
from veupath_chatbot.ai.tools.execution_tools import ExecutionTools
from veupath_chatbot.ai.tools.result_tools import ResultTools
from veupath_chatbot.ai.tools.strategy_tools import StrategyTools
from veupath_chatbot.ai.tools.unified_registry import UnifiedToolRegistryMixin
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONArray, JSONObject
from veupath_chatbot.services.research import (
    LiteratureSearchService,
    WebSearchService,
)
from veupath_chatbot.services.strategies.session_factory import build_strategy_session

logger = get_logger(__name__)


def _merge_auto_build(original_text: str | None, extra: JSONObject) -> str:
    """Merge auto-build data into the tool result as valid JSON.

    Keeps the original tool result fields intact and adds/overwrites keys
    from ``extra``.  If the original text isn't parseable JSON, wraps
    ``extra`` in a standalone JSON string.
    """
    parsed: JSONObject = {}
    if original_text:
        try:
            loaded = json.loads(original_text)
            if isinstance(loaded, dict):
                parsed = loaded
        except json.JSONDecodeError, TypeError:
            pass
    parsed.update(extra)
    return json.dumps(parsed)


class PathfinderAgent(UnifiedToolRegistryMixin, Kani):
    """Unified VEuPathDB Strategy Agent — research, planning, and execution.

    Combines executor (graph building, delegation, WDK execution) and
    planner (gene lookup, control tests, parameter optimization, artifacts)
    capabilities in a single agent. The model decides per-turn whether to
    research/plan or build/execute.
    """

    functions: dict[str, AIFunction]

    def __init__(
        self,
        engine: BaseEngine,
        site_id: str,
        user_id: UUID | None = None,
        chat_history: list[ChatMessage] | None = None,
        strategy_graph: JSONObject | None = None,
        selected_nodes: JSONObject | None = None,
        mentioned_context: str | None = None,
        disable_rag: bool = False,
        desired_response_tokens: int | None = None,
    ) -> None:
        self.site_id = site_id
        self.user_id = user_id
        self.strategy_session = build_strategy_session(
            site_id=site_id, strategy_graph=strategy_graph
        )

        self.catalog_tools = CatalogTools()
        self.catalog_rag_tools = CatalogRagTools(site_id=site_id, disabled=disable_rag)
        self.example_plans_rag_tools = ExamplePlansRagTools(
            site_id=site_id, disabled=disable_rag
        )
        self.strategy_tools = StrategyTools(self.strategy_session)
        self.execution_tools = ExecutionTools(self.strategy_session)
        self.result_tools = ResultTools(self.strategy_session)
        self.conversation_tools = ConversationTools(self.strategy_session, user_id)
        self.web_search_service = WebSearchService()
        self.literature_search_service = LiteratureSearchService()

        system_prompt = build_agent_system_prompt(
            site_id=site_id,
            selected_nodes=selected_nodes,
            mentioned_context=mentioned_context,
        )

        super().__init__(
            engine=engine,
            system_prompt=system_prompt,
            chat_history=chat_history or [],
            desired_response_tokens=desired_response_tokens,
        )
        self.event_queue: asyncio.Queue[JSONObject] | None = None
        # Cancellation signal — set by stream_chat when the client disconnects.
        # Required by OptimizationToolsMixin for long-running optimization runs.
        self._cancel_event = asyncio.Event()
        # Track the gene set created by auto-build so rebuilds reuse it.
        self._auto_build_gene_set_id: str | None = None

    async def _emit_event(self, event: JSONObject) -> None:
        if self.event_queue is not None:
            await self.event_queue.put(event)

    # ── Auto-build hook ────────────────────────────────────────────
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

        if len(graph.roots) != 1:
            # Cannot auto-build with multiple (or zero) roots — inform the model.
            skip_data: JSONObject = {
                "autoBuild": {
                    "ok": False,
                    "skipped": True,
                    "reason": "multiple_roots",
                    "rootCount": len(graph.roots),
                },
            }
            if graph.wdk_step_ids:
                auto_build_dict = cast(JSONObject, skip_data["autoBuild"])
                auto_build_dict["existingWdkStepIds"] = dict(graph.wdk_step_ids)
            result.message.content = _merge_auto_build(result.message.text, skip_data)
            return result

        # Graph has exactly one root — build (or rebuild after mutation).
        try:
            from veupath_chatbot.services.strategies.build import (
                build_strategy_for_site,
            )

            build_result = await build_strategy_for_site(
                graph=graph,
                site_id=self.site_id,
                strategy_name=graph.name,
            )

            # Enrich the tool result message with build data.
            build_data: JSONObject = {
                "autoBuild": {
                    "ok": True,
                    "wdkStrategyId": build_result.wdk_strategy_id,
                    "wdkUrl": build_result.wdk_url,
                    "counts": {str(k): v for k, v in build_result.counts.items()},
                    "rootCount": build_result.root_count,
                    "zeroStepIds": cast(JSONArray, build_result.zero_step_ids),
                },
            }

            # Create or reuse the gene set for this strategy.
            if build_result.wdk_strategy_id is not None and self.user_id is not None:
                try:
                    from veupath_chatbot.services.gene_sets import GeneSetService
                    from veupath_chatbot.services.gene_sets.store import (
                        get_gene_set_store,
                    )

                    store = get_gene_set_store()
                    svc = GeneSetService(store)

                    # Reuse: (1) tracked from prior build in this session,
                    # or (2) existing set for same WDK strategy ID.
                    gs = None
                    if self._auto_build_gene_set_id:
                        gs = store.get(self._auto_build_gene_set_id)
                    if gs is None:
                        gs = svc.find_by_wdk_strategy(
                            self.user_id, build_result.wdk_strategy_id
                        )

                    if gs is not None:
                        gs.wdk_strategy_id = build_result.wdk_strategy_id
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
                            wdk_strategy_id=build_result.wdk_strategy_id,
                            record_type=graph.record_type,
                        )
                        await svc.flush(gs.id)

                    self._auto_build_gene_set_id = gs.id
                    ab = cast(JSONObject, build_data["autoBuild"])
                    ab["geneSetCreated"] = {
                        "id": gs.id,
                        "name": gs.name,
                        "geneCount": len(gs.gene_ids),
                        "source": gs.source,
                        "siteId": gs.site_id,
                    }
                except Exception as gs_exc:
                    logger.warning("Gene set creation failed", error=str(gs_exc))

            # Emit strategy_link so frontend updates immediately.
            await self._emit_event(
                {
                    "type": "strategy_link",
                    "data": {
                        "graphId": graph.id,
                        "wdkStrategyId": build_result.wdk_strategy_id,
                        "wdkUrl": build_result.wdk_url,
                        "name": graph.name,
                        "isSaved": False,
                    },
                }
            )

            # Emit graph_snapshot with updated WDK step IDs and counts
            # so the frontend graph reflects the built state.
            await self._emit_event(
                {
                    "type": "graph_snapshot",
                    "data": {
                        "graphId": graph.id,
                        "graphSnapshot": self.strategy_tools._build_graph_snapshot(
                            graph
                        ),
                    },
                }
            )

            # Merge build data into the tool result JSON so parse_jsonish
            # in streaming.py can still parse it and emit strategy events.
            result.message.content = _merge_auto_build(result.message.text, build_data)

        except Exception as exc:
            result.message.content = _merge_auto_build(
                result.message.text,
                {"autoBuild": {"ok": False, "error": str(exc)}},
            )
            logger.warning("Auto-build failed", error=str(exc))

        return result

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
        from veupath_chatbot.ai.engines.mock import MockEngine

        if isinstance(self.engine, MockEngine):

            def _engine_factory() -> BaseEngine:
                return MockEngine(site_id=self.site_id)

        else:
            # Build sub-kani engines from the same provider as the parent agent
            # so delegation works even when the user only has one API key.
            from veupath_chatbot.ai.agents.factory import create_engine
            from veupath_chatbot.ai.models.catalog import get_model_entry

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
            site_id=self.site_id,
            strategy_session=self.strategy_session,
            strategy_tools=self.strategy_tools,
            emit_event=self._emit_event,
            chat_history=self.chat_history,
            plan=plan,
            engine_factory=_engine_factory,
        )


# Cheapest model per provider for sub-kani delegation.
_SUBKANI_MODEL_BY_PROVIDER: dict[str, str | None] = {
    "openai": None,  # None = use settings.subkani_model (gpt-4.1-mini)
    "anthropic": "anthropic/claude-haiku-4-5",
    "google": "google/gemini-2.5-pro",
    "ollama": None,
}

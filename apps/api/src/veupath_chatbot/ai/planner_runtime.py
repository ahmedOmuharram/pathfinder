"""Planning-mode agent runtime."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from uuid import UUID

from kani import ChatMessage, Kani
from kani.engines.base import BaseEngine

from veupath_chatbot.ai.planner_prompt import build_planner_system_prompt
from veupath_chatbot.ai.strategy_session_factory import build_strategy_session
from veupath_chatbot.ai.tools.catalog_rag_tools import CatalogRagTools
from veupath_chatbot.ai.tools.catalog_tools import CatalogTools
from veupath_chatbot.ai.tools.example_plans_rag_tools import ExamplePlansRagTools
from veupath_chatbot.ai.tools.planner_registry import PlannerToolRegistryMixin
from veupath_chatbot.platform.types import JSONArray, JSONObject
from veupath_chatbot.services.research import (
    LiteratureSearchService,
    WebSearchService,
)


class PathfinderPlannerAgent(PlannerToolRegistryMixin, Kani):  # type: ignore[misc]
    """Planner agent: cooperative strategy planning (no graph mutation by default)."""

    def __init__(
        self,
        engine: BaseEngine,
        site_id: str,
        user_id: UUID | None = None,
        chat_history: list[ChatMessage] | None = None,
        strategy_graph: JSONObject | None = None,
        selected_nodes: JSONObject | None = None,
        delegation_draft_artifact: JSONObject | None = None,
        plan_session_id: UUID | None = None,
        get_plan_session_artifacts: Callable[[], Awaitable[JSONArray]] | None = None,
    ) -> None:
        self.site_id = site_id
        self.user_id = user_id
        self.plan_session_id = plan_session_id
        self.get_plan_session_artifacts = get_plan_session_artifacts

        # Keep session context so planners can reference existing graph state if needed.
        self.strategy_session = build_strategy_session(
            site_id=site_id, strategy_graph=strategy_graph
        )

        self.catalog_tools = CatalogTools()
        self.catalog_rag_tools = CatalogRagTools(site_id=site_id)
        self.example_plans_rag_tools = ExamplePlansRagTools(site_id=site_id)
        self.web_search_service = WebSearchService()
        self.literature_search_service = LiteratureSearchService()

        system_prompt = build_planner_system_prompt(
            site_id=site_id,
            selected_nodes=selected_nodes,
            delegation_draft_artifact=delegation_draft_artifact,
        )

        super().__init__(
            engine=engine,
            system_prompt=system_prompt,
            chat_history=chat_history or [],
        )

        # For consistency with executor streaming (sub-kani uses this too).
        self.event_queue: asyncio.Queue[JSONObject] | None = None

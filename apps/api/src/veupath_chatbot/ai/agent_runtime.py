"""Kani agent runtime (class + subkani orchestration)."""

import asyncio
from typing import Any
from uuid import UUID

from kani import ChatMessage, Kani, ai_function
from kani.engines.openai import OpenAIEngine

from veupath_chatbot.ai.subkani.orchestrator import (
    delegate_strategy_subtasks as subkani_delegate_strategy_subtasks,
)
from veupath_chatbot.ai.system_prompt import build_agent_system_prompt
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.domain.strategy.ast import from_dict
from veupath_chatbot.services.strategy_session import StrategyGraph, StrategySession

from veupath_chatbot.ai.tools.catalog_tools import CatalogTools
from veupath_chatbot.ai.tools.conversation_tools import ConversationTools
from veupath_chatbot.ai.tools.execution_tools import ExecutionTools
from veupath_chatbot.ai.tools.registry import AgentToolRegistryMixin
from veupath_chatbot.ai.tools.strategy_tools import StrategyTools

logger = get_logger(__name__)


class PathfinderAgent(AgentToolRegistryMixin, Kani):
    """VEuPathDB Strategy Builder Agent with Kani tools."""

    def __init__(
        self,
        engine: OpenAIEngine,
        site_id: str,
        user_id: UUID | None = None,
        chat_history: list[ChatMessage] | None = None,
        strategy_graph: dict | None = None,
        selected_nodes: dict | None = None,
    ) -> None:
        self.site_id = site_id

        self.strategy_session = StrategySession(site_id)
        if strategy_graph:
            graph_id = str(strategy_graph.get("id") or strategy_graph.get("graphId"))
            name = strategy_graph.get("name") or "Draft Strategy"
            plan = strategy_graph.get("plan")
            graph = StrategyGraph(graph_id, name, site_id)
            if plan:
                try:
                    strategy = from_dict(plan)
                    graph.current_strategy = strategy
                    graph.name = strategy.name or name
                    graph.steps = {step.id: step for step in strategy.get_all_steps()}
                    graph.last_step_id = strategy.root.id
                    graph.save_history(f"Loaded graph: {strategy.name or name}")
                except Exception as e:
                    logger.warning(
                        "Failed to load graph plan",
                        error=str(e),
                        graph_id=graph_id,
                    )
            self.strategy_session.add_graph(graph)
        if not self.strategy_session.get_graph(None):
            self.strategy_session.create_graph("Draft Strategy")

        self.catalog_tools = CatalogTools()
        self.strategy_tools = StrategyTools(self.strategy_session)
        self.execution_tools = ExecutionTools(self.strategy_session)
        self.conversation_tools = ConversationTools(self.strategy_session, user_id)

        system_prompt = build_agent_system_prompt(site_id=site_id, selected_nodes=selected_nodes)

        super().__init__(
            engine=engine,
            system_prompt=system_prompt,
            chat_history=chat_history or [],
        )
        self.event_queue: asyncio.Queue | None = None

    async def _emit_event(self, event: dict) -> None:
        if self.event_queue is not None:
            await self.event_queue.put(event)

    @ai_function()
    async def delegate_strategy_subtasks(
        self,
        goal: str,
        subtasks: list[dict[str, Any] | str] | None = None,
        post_plan: str | None = None,
        combines: list[dict[str, Any]] | None = None,
    ) -> dict:
        """Spawn sub-kanis to discover searches and parameters."""
        return await subkani_delegate_strategy_subtasks(
            goal=goal,
            site_id=self.site_id,
            strategy_session=self.strategy_session,
            strategy_tools=self.strategy_tools,
            emit_event=self._emit_event,
            chat_history=self.chat_history,
            subtasks=subtasks,
            post_plan=post_plan,
            combines=combines,
        )


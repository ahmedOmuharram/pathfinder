"""Kani agent runtime (class + subkani orchestration)."""

import asyncio
from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from kani import AIParam, ChatMessage, ai_function
from kani.engines.base import BaseEngine

if TYPE_CHECKING:
    from veupath_chatbot.ai.stubs.kani import Kani
else:
    from kani import Kani

from veupath_chatbot.ai.strategy_session_factory import build_strategy_session
from veupath_chatbot.ai.subkani.orchestrator import (
    delegate_strategy_subtasks as subkani_delegate_strategy_subtasks,
)
from veupath_chatbot.ai.system_prompt import build_agent_system_prompt
from veupath_chatbot.ai.tools.catalog_rag_tools import CatalogRagTools
from veupath_chatbot.ai.tools.catalog_tools import CatalogTools
from veupath_chatbot.ai.tools.conversation_tools import ConversationTools
from veupath_chatbot.ai.tools.example_plans_rag_tools import ExamplePlansRagTools
from veupath_chatbot.ai.tools.execution_tools import ExecutionTools
from veupath_chatbot.ai.tools.registry import AgentToolRegistryMixin
from veupath_chatbot.ai.tools.strategy_tools import StrategyTools
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject

logger = get_logger(__name__)


class PathfinderAgent(AgentToolRegistryMixin, Kani):
    """VEuPathDB Strategy Builder Agent with Kani tools."""

    def __init__(
        self,
        engine: BaseEngine,
        site_id: str,
        user_id: UUID | None = None,
        chat_history: list[ChatMessage] | None = None,
        strategy_graph: JSONObject | None = None,
        selected_nodes: JSONObject | None = None,
    ) -> None:
        self.site_id = site_id
        self.strategy_session = build_strategy_session(
            site_id=site_id, strategy_graph=strategy_graph
        )

        self.catalog_tools = CatalogTools()
        self.catalog_rag_tools = CatalogRagTools(site_id=site_id)
        self.example_plans_rag_tools = ExamplePlansRagTools(site_id=site_id)
        self.strategy_tools = StrategyTools(self.strategy_session)
        self.execution_tools = ExecutionTools(self.strategy_session)
        self.conversation_tools = ConversationTools(self.strategy_session, user_id)

        system_prompt = build_agent_system_prompt(
            site_id=site_id, selected_nodes=selected_nodes
        )

        super().__init__(
            engine=engine,
            system_prompt=system_prompt,
            chat_history=chat_history or [],
        )
        self.event_queue: asyncio.Queue[JSONObject] | None = None

    async def _emit_event(self, event: JSONObject) -> None:
        if self.event_queue is not None:
            await self.event_queue.put(event)

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
        return await subkani_delegate_strategy_subtasks(
            goal=goal,
            site_id=self.site_id,
            strategy_session=self.strategy_session,
            strategy_tools=self.strategy_tools,
            emit_event=self._emit_event,
            chat_history=self.chat_history,
            plan=plan,
        )

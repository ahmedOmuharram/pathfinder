"""Sub-agent used for decomposed strategy-building tasks."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from kani import ChatMessage
from kani.engines.openai import OpenAIEngine

if TYPE_CHECKING:
    from veupath_chatbot.ai.stubs.kani import Kani
else:
    from kani import Kani

from veupath_chatbot.ai.tools.catalog_rag_tools import CatalogRagTools
from veupath_chatbot.ai.tools.catalog_tools import CatalogTools
from veupath_chatbot.ai.tools.conversation_tools import ConversationTools
from veupath_chatbot.ai.tools.example_plans_rag_tools import ExamplePlansRagTools
from veupath_chatbot.ai.tools.execution_tools import ExecutionTools
from veupath_chatbot.ai.tools.registry import AgentToolRegistryMixin
from veupath_chatbot.ai.tools.strategy_tools import StrategyTools
from veupath_chatbot.domain.strategy.session import StrategySession
from veupath_chatbot.platform.types import JSONObject, JSONValue


def _load_subtask_system_prompt() -> str:
    prompt_path = Path(__file__).parent / "prompts" / "subtask.md"
    return prompt_path.read_text()


class SubtaskAgent(AgentToolRegistryMixin, Kani):
    """Sub-kani agent for search discovery and parameter lookup."""

    def _combined_result(
        self,
        *,
        rag: JSONValue,
        wdk: JSONValue,
        rag_note: str | None = None,
        wdk_note: str | None = None,
    ) -> JSONObject:
        return {
            "rag": {"data": rag, "note": rag_note or ""},
            "wdk": {"data": wdk, "note": wdk_note or ""},
        }

    def __init__(
        self,
        engine: OpenAIEngine,
        site_id: str,
        session: StrategySession,
        graph_id: str,
        chat_history: list[ChatMessage],
    ) -> None:
        self.site_id = site_id
        self.graph_id = graph_id
        # Keep naming consistent with the main agent; tools use these objects.
        self.strategy_session = session
        self.catalog_tools = CatalogTools()
        self.catalog_rag_tools = CatalogRagTools(site_id=site_id)
        self.example_plans_rag_tools = ExamplePlansRagTools(site_id=site_id)
        self.strategy_tools = StrategyTools(self.strategy_session)
        self.execution_tools = ExecutionTools(self.strategy_session)
        # Sub-agent has no user identity; keep tool surface identical to main agent.
        self.conversation_tools = ConversationTools(self.strategy_session, user_id=None)
        super().__init__(
            engine=engine,
            system_prompt=_load_subtask_system_prompt(),
            chat_history=chat_history,
        )

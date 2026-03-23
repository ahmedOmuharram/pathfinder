"""Sub-agent used for decomposed strategy-building tasks."""

from pathlib import Path

from kani import ChatMessage, Kani
from kani.engines.base import BaseEngine

from veupath_chatbot.ai.tools.catalog_tools import CatalogTools
from veupath_chatbot.ai.tools.conversation_tools import ConversationTools
from veupath_chatbot.ai.tools.execution_tools import ExecutionTools
from veupath_chatbot.ai.tools.registry import AgentToolRegistryMixin
from veupath_chatbot.ai.tools.result_tools import ResultTools
from veupath_chatbot.ai.tools.strategy_tools import StrategyTools
from veupath_chatbot.domain.strategy.session import StrategySession


def _load_subtask_system_prompt() -> str:
    prompt_path = Path(__file__).parent.parent / "prompts" / "subtask.md"
    return prompt_path.read_text()


class SubtaskAgent(AgentToolRegistryMixin, Kani):
    """Sub-kani agent for search discovery and parameter lookup."""

    def __init__(
        self,
        engine: BaseEngine,
        site_id: str,
        session: StrategySession,
        graph_id: str,
        chat_history: list[ChatMessage],
    ) -> None:
        self.site_id = site_id
        self.graph_id = graph_id
        # Keep naming consistent with the main agent; tools use these objects.
        self.strategy_session = session
        self.catalog_tools = CatalogTools(site_id)
        self.strategy_tools = StrategyTools(self.strategy_session)
        self.execution_tools = ExecutionTools(self.strategy_session)
        self.result_tools = ResultTools(self.strategy_session)
        # Sub-agent has no user identity; keep tool surface identical to main agent.
        self.conversation_tools = ConversationTools(self.strategy_session, user_id=None)
        super().__init__(
            engine=engine,
            system_prompt=_load_subtask_system_prompt(),
            chat_history=chat_history,
        )

"""Sub-agent used for decomposed strategy-building tasks."""

from __future__ import annotations

from pathlib import Path

from kani import ChatMessage, Kani, ai_function
from kani.engines.openai import OpenAIEngine

from veupath_chatbot.ai.tools.catalog_tools import CatalogTools
from veupath_chatbot.ai.tools.strategy_tools import StrategyTools
from veupath_chatbot.services.strategy_session import StrategySession


def _load_subtask_system_prompt() -> str:
    prompt_path = Path(__file__).parent / "prompts" / "subtask.md"
    return prompt_path.read_text()


class SubtaskAgent(Kani):
    """Sub-kani agent for search discovery and parameter lookup."""

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
        self.catalog_tools = CatalogTools()
        self.strategy_tools = StrategyTools(session)
        super().__init__(
            engine=engine,
            system_prompt=_load_subtask_system_prompt(),
            chat_history=chat_history,
        )

    @ai_function()
    async def get_record_types(self):
        return await self.catalog_tools.get_record_types(self.site_id)

    @ai_function()
    async def list_searches(self, record_type: str):
        return await self.catalog_tools.list_searches(self.site_id, record_type)

    @ai_function()
    async def search_for_searches(self, record_type: str, query: str):
        return await self.catalog_tools.search_for_searches(self.site_id, record_type, query)

    @ai_function()
    async def get_search_parameters(self, record_type: str, search_name: str):
        return await self.catalog_tools.get_search_parameters(self.site_id, record_type, search_name)

    @ai_function()
    async def create_search_step(
        self,
        record_type: str,
        search_name: str,
        parameters: dict | None = None,
        display_name: str | None = None,
        graph_id: str | None = None,
    ):
        return await self.strategy_tools.create_search_step(
            record_type=record_type,
            search_name=search_name,
            parameters=parameters,
            display_name=display_name,
            graph_id=graph_id or self.graph_id,
        )

    @ai_function()
    async def combine_steps(
        self,
        left_step_id: str,
        right_step_id: str,
        operator: str,
        display_name: str | None = None,
        upstream: int | None = None,
        downstream: int | None = None,
        graph_id: str | None = None,
    ):
        return await self.strategy_tools.combine_steps(
            left_step_id=left_step_id,
            right_step_id=right_step_id,
            operator=operator,
            display_name=display_name,
            upstream=upstream,
            downstream=downstream,
            graph_id=graph_id or self.graph_id,
        )

    @ai_function()
    async def find_orthologs(
        self,
        input_step_id: str,
        target_organisms: list[str] | str,
        is_syntenic: str | bool | None = None,
        display_name: str | None = None,
        graph_id: str | None = None,
    ):
        return await self.strategy_tools.find_orthologs(
            input_step_id=input_step_id,
            target_organisms=target_organisms,
            is_syntenic=is_syntenic,
            display_name=display_name,
            graph_id=graph_id or self.graph_id,
        )


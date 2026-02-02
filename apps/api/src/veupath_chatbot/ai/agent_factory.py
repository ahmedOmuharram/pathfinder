"""Factory helpers for constructing the agent and its engine."""

from __future__ import annotations

from uuid import UUID

from kani import ChatMessage
from kani.engines.openai import OpenAIEngine

from veupath_chatbot.platform.config import get_settings

from .agent_runtime import PathfinderAgent


def create_engine() -> OpenAIEngine:
    settings = get_settings()
    return OpenAIEngine(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        temperature=settings.openai_temperature,
        top_p=settings.openai_top_p,
    )


def create_agent(
    site_id: str,
    user_id: UUID | None = None,
    chat_history: list[ChatMessage] | None = None,
    strategy_graph: dict | None = None,
    selected_nodes: dict | None = None,
) -> PathfinderAgent:
    """Create a new Pathfinder agent instance."""
    engine = create_engine()
    return PathfinderAgent(
        engine=engine,
        site_id=site_id,
        user_id=user_id,
        chat_history=chat_history,
        strategy_graph=strategy_graph,
        selected_nodes=selected_nodes,
    )


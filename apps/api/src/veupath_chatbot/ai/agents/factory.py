"""Agent factory -- creates PathfinderAgent instances.

Engine creation logic lives in engine_factory.py to avoid circular imports
(executor.py needs create_engine, factory.py needs PathfinderAgent).
"""

from uuid import UUID

from kani import ChatMessage

from veupath_chatbot.ai.agents.engine_factory import (
    EngineConfig,
    create_engine,
    resolve_effective_model_id,
)
from veupath_chatbot.platform.types import JSONObject

from .executor import PathfinderAgent

# Re-export for backward compatibility with existing callers.
__all__ = [
    "EngineConfig",
    "PathfinderAgent",
    "create_agent",
    "create_engine",
    "resolve_effective_model_id",
]


def create_agent(
    site_id: str,
    user_id: UUID | None = None,
    chat_history: list[ChatMessage] | None = None,
    strategy_graph: JSONObject | None = None,
    selected_nodes: JSONObject | None = None,
    *,
    engine_config: EngineConfig | None = None,
    mentioned_context: str | None = None,
    disable_rag: bool = False,
    response_tokens: int | None = None,
) -> PathfinderAgent:
    """Create a unified Pathfinder agent instance."""
    engine = create_engine(
        engine_config or EngineConfig(),
        site_id=site_id,
    )
    return PathfinderAgent(
        engine=engine,
        site_id=site_id,
        user_id=user_id,
        chat_history=chat_history,
        strategy_graph=strategy_graph,
        selected_nodes=selected_nodes,
        mentioned_context=mentioned_context,
        disable_rag=disable_rag,
        desired_response_tokens=response_tokens,
    )

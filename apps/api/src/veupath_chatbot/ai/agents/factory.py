"""Agent factory -- creates PathfinderAgent instances.

Engine creation logic lives in engine_factory.py to avoid circular imports
(executor.py needs create_engine, factory.py needs PathfinderAgent).
"""

from veupath_chatbot.ai.agents.engine_factory import (
    EngineConfig,
    create_engine,
    resolve_effective_model_id,
)

from .executor import AgentContext, PathfinderAgent

__all__ = [
    "AgentContext",
    "EngineConfig",
    "PathfinderAgent",
    "create_agent",
    "create_engine",
    "resolve_effective_model_id",
]


def create_agent(
    context: AgentContext,
    *,
    engine_config: EngineConfig | None = None,
) -> PathfinderAgent:
    """Create a unified Pathfinder agent instance."""
    engine = create_engine(
        engine_config or EngineConfig(),
        site_id=context.site_id,
    )
    return PathfinderAgent(engine=engine, context=context)

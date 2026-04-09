"""Standalone strategy graph inspection tools for pydantic-ai migration.

Each function takes ``RunContext[AgentDeps]`` and mirrors the original
:class:`StrategyGraphOps` methods exactly.
"""

from pydantic_ai import RunContext

from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.ai.tools.standalone._graph_helpers import serialize_step
from pathfinder.ai.tools.standalone._validation_helpers import (
    get_graph,
    graph_not_found,
)
from pathfinder.platform.logging import get_logger
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.platform.tool_errors import ToolErrorPayload
from pathfinder.platform.types import JSONValue
from pathfinder.services.strategies.schemas import StepResponse

logger = get_logger(__name__)


class StrategySummaryResponse(CamelModel):
    """Summary metadata for a strategy graph."""

    graph_id: str
    graph_name: str | None = None
    record_type: str | None = None
    wdk_strategy_id: JSONValue = None
    is_built: bool = False
    step_count: int = 0
    description: str | None = None
    steps: list[StepResponse] | None = None


async def get_strategy(
    ctx: RunContext[AgentDeps],
    graph_id: str | None = None,
    *,
    summary_only: bool = True,
) -> StrategySummaryResponse | ToolErrorPayload:
    """Get the current strategy graph -- summary metadata or full step details.

    By default returns a lightweight summary (step count, record type, build status).
    Pass summary_only=false for per-step details including WDK step IDs and estimated
    result counts.
    """
    deps = ctx.deps
    session = deps.strategy_session

    graph = get_graph(session, graph_id)
    if not graph:
        return graph_not_found(graph_id)

    sync_state = session.sync_state
    wdk_strategy_id = sync_state.wdk_strategy_id if sync_state else None

    steps: list[StepResponse] | None = None
    if not summary_only:
        steps = [
            serialize_step(graph, step, sync_state)
            for step in graph.steps.values()
        ]

    return StrategySummaryResponse(
        graph_id=graph.id,
        graph_name=graph.name,
        record_type=graph.record_type,
        wdk_strategy_id=wdk_strategy_id,
        is_built=wdk_strategy_id is not None,
        step_count=len(graph.steps),
        description=graph.description,
        steps=steps,
    )

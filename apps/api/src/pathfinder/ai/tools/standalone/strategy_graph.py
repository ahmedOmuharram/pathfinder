"""Standalone strategy graph inspection tools for pydantic-ai migration.

Each function takes ``RunContext[AgentDeps]`` and mirrors the original
:class:`StrategyGraphOps` methods exactly.
"""

from assistant_core.graph.tool_summary import with_summary
from assistant_core.platform.logging import get_logger
from assistant_core.platform.pydantic_base import CamelModel
from pydantic import JsonValue
from pydantic_ai import RunContext
from pydantic_ai.messages import ToolReturn

from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.standalone._graph_helpers import serialize_step
from pathfinder.ai.tools.standalone._validation_helpers import (
    get_graph,
    graph_not_found,
)
from pathfinder.domain.strategy.revision import strategy_revision
from pathfinder.domain.strategy.session import StrategyGraph
from pathfinder.domain.strategy.types import SyncStateProtocol
from pathfinder.platform.tool_errors import ToolErrorPayload
from pathfinder.services.strategies.schemas import StepResponse

logger = get_logger(__name__)


def _root_count(graph: StrategyGraph, sync_state: SyncStateProtocol | None) -> int:
    """The root step's WDK count. Zero when no single root carries one."""
    if sync_state is None or len(graph.roots) != 1:
        return 0
    return sync_state.step_counts.get(next(iter(graph.roots))) or 0


class StrategySummaryResponse(CamelModel):
    """Summary metadata for a strategy graph."""

    graph_id: str
    graph_name: str | None = None
    record_type: str | None = None
    wdk_strategy_id: JsonValue = None
    is_built: bool = False
    step_count: int = 0
    description: str | None = None
    steps: list[StepResponse] | None = None
    revision: str = ""
    """Fingerprint of the strategy's inputs; pass to ``apply_operations``.

    Hashes search names, parameters, operators and tree shape only, so a
    refreshed count never looks like an edit. Empty for no strategy.
    """


async def get_strategy(
    ctx: RunContext[AgentDeps],
    graph_id: str | None = None,
    *,
    summary_only: bool = True,
) -> ToolReturn[StrategySummaryResponse | ToolErrorPayload]:
    """Get the current strategy graph -- summary metadata or full step details.

    By default returns a lightweight summary (step count, record type, build status).
    Pass summary_only=false for per-step details including WDK step IDs and estimated
    result counts.
    """
    deps = ctx.deps
    session = deps.strategy_session

    graph = get_graph(session, graph_id)
    if not graph:
        return with_summary(
            graph_not_found(graph_id),
            "No strategy yet",
            ctx=ctx,
            status="empty",
        )

    sync_state = session.sync_state
    wdk_strategy_id = sync_state.wdk_strategy_id if sync_state else None

    steps: list[StepResponse] | None = None
    if not summary_only:
        steps = [
            serialize_step(graph, step, sync_state) for step in graph.steps.values()
        ]

    summary = StrategySummaryResponse(
        graph_id=graph.id,
        graph_name=graph.name,
        record_type=graph.record_type,
        wdk_strategy_id=wdk_strategy_id,
        is_built=wdk_strategy_id is not None,
        step_count=len(graph.steps),
        description=graph.description,
        steps=steps,
        revision=strategy_revision(graph.to_strategy_ast(sync_state=sync_state)),
    )
    if not graph.steps:
        return with_summary(summary, "No strategy yet", ctx=ctx, status="empty")
    genes = _root_count(graph, sync_state)
    return with_summary(
        summary,
        f"{len(graph.steps)} steps, {genes:,} genes",
        ctx=ctx,
        status="ok" if genes else "empty",
    )

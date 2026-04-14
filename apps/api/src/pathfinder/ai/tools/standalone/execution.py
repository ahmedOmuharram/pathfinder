"""Standalone execution tools for pydantic-ai agents.

Provides:
- ``get_estimated_size`` -- get result count for a built step
"""

from pydantic_ai import RunContext

from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.standalone._result_models import EstimatedSizeResult
from pathfinder.platform.errors import AppError, ErrorCode
from pathfinder.platform.tool_errors import ToolErrorPayload, tool_error
from pathfinder.services.strategies.build import get_estimated_size_for_site


async def get_estimated_size(
    ctx: RunContext[AgentDeps],
    wdk_step_id: int,
    wdk_strategy_id: int | None = None,
) -> EstimatedSizeResult | ToolErrorPayload:
    """Get the result count for a built step.

    The step must already be built in WDK (via auto-build or import).
    For imported WDK strategies, provide wdk_strategy_id.

    Args:
        wdk_step_id: WDK step ID. The step must be built in WDK first.
        wdk_strategy_id: WDK strategy ID (required for imported strategies).
    """
    try:
        result = await get_estimated_size_for_site(
            ctx.deps.strategy_session.site_id, wdk_step_id, wdk_strategy_id
        )
    except (AppError, OSError) as e:
        message = str(e)
        if wdk_strategy_id is None:
            message = f"{message} (try providing wdk_strategy_id)"
        return tool_error(ErrorCode.WDK_ERROR, message)
    return EstimatedSizeResult(step_id=result.step_id, count=result.count)

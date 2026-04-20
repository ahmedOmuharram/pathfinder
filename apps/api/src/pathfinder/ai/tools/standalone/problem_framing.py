from __future__ import annotations

from pydantic_ai import RunContext
from pydantic_ai.messages import ToolReturn

from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.graph.state import ProblemFrame
from pathfinder.ai.tools.standalone._stream_parts import problem_frame_chunk
from pathfinder.platform.pydantic_base import CamelModel


class ProblemFrameResponse(CamelModel):
    problem_frame: ProblemFrame


async def set_problem_frame(
    ctx: RunContext[AgentDeps],
    frame: ProblemFrame,
) -> ToolReturn[ProblemFrameResponse]:
    """Save the current problem frame for downstream discovery and planning.

    Call this exactly once near the end of scoping. If the request is still
    ambiguous, set ``ready_for_wdk_discovery`` to false and include concise
    blocking questions. If it is clear enough to explore WDK, set it to true
    and record any assumptions the next phases should preserve.
    """
    confidence = max(0.0, min(1.0, frame.confidence))
    normalized = frame.model_copy(update={"confidence": confidence})
    ctx.deps.problem_frame = normalized
    return ToolReturn(
        return_value=ProblemFrameResponse(problem_frame=normalized),
        metadata=[problem_frame_chunk(normalized, site_id=ctx.deps.site_id)],
    )

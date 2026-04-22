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
    """Save the problem frame. ONE-SHOT — after this call the tool is
    removed from your toolset and you cannot amend the frame further in this
    turn. Do all your ``think``/``web_search``/``literature_search`` BEFORE
    calling this. Populate ``blocking_questions`` now if the prompt is
    ambiguous; you will not get another chance.
    """
    confidence = max(0.0, min(1.0, frame.confidence))
    normalized = frame.model_copy(update={"confidence": confidence})
    ctx.deps.problem_frame = normalized
    ctx.deps.problem_frame_set_this_run = True
    return ToolReturn(
        return_value=ProblemFrameResponse(problem_frame=normalized),
        metadata=[problem_frame_chunk(normalized, site_id=ctx.deps.site_id)],
    )

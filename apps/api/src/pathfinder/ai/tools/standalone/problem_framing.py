"""Problem-framing tools for the scoping phase."""

from __future__ import annotations

from pydantic import Field
from pydantic_ai import RunContext
from pydantic_ai.messages import ToolReturn

from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.ai.orchestration.phase_results import (
    ProblemFrame,
    ScopingResult,
)
from pathfinder.ai.tools.standalone._stream_parts import problem_frame_chunk
from pathfinder.platform.pydantic_base import CamelModel


class ProblemFrameResponse(CamelModel):
    """Tool response persisted into the transcript and emitted as SSE."""

    problem_frame: ProblemFrame = Field(alias="problemFrame")


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
    existing_decision = (
        ctx.deps.scoping_result.decision
        if ctx.deps.scoping_result is not None
        else None
    )
    ctx.deps.problem_frame = normalized
    ctx.deps.scoping_result = ScopingResult(
        problem_frame=normalized,
        decision=existing_decision,
    )
    return ToolReturn(
        return_value=ProblemFrameResponse(problemFrame=normalized),
        metadata=[problem_frame_chunk(normalized, site_id=ctx.deps.site_id)],
    )

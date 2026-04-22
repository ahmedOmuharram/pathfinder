"""Internal: exposes stream-part payload models in the OpenAPI schema.

These models aren't used by any real endpoint — this module only exists
so they appear under components/schemas for type generation on the frontend.
Transitive types (GraphNode, GraphEdge, PlannedStep) are auto-included via
$ref from their parent schemas and do not need explicit entries.
"""

from fastapi import APIRouter
from shared_py.stream_parts.background_task import (
    BackgroundTaskStarted,
    TaskCompleted,
    TaskProgress,
)
from shared_py.stream_parts.gene_set import GeneSet
from shared_py.stream_parts.graph import (
    GraphCleared,
    GraphPlan,
    GraphSnapshot,
)
from shared_py.stream_parts.optimization import OptimizationSnapshot
from shared_py.stream_parts.phase import PhaseChange
from shared_py.stream_parts.plan import (
    DecisionPresented,
    PlanArtifact,
    PlanUpdate,
)
from shared_py.stream_parts.problem_frame import ProblemFrame
from shared_py.stream_parts.strategy import (
    StrategyLink,
    StrategyMeta,
    StrategyPatch,
)
from shared_py.stream_parts.turn_usage import TurnUsage

from pathfinder.platform.pydantic_base import CamelModel

router = APIRouter(prefix="/api/v1/internal/stream-parts", tags=["internal"])


class StreamPartsSchemaIndex(CamelModel):
    """Index of stream-part payload schemas. Never called — exists for OpenAPI generation."""

    graph_snapshot: GraphSnapshot | None = None
    graph_plan: GraphPlan | None = None
    graph_cleared: GraphCleared | None = None
    strategy_patch: StrategyPatch | None = None
    strategy_meta: StrategyMeta | None = None
    strategy_link: StrategyLink | None = None
    plan_artifact: PlanArtifact | None = None
    plan_update: PlanUpdate | None = None
    decision_presented: DecisionPresented | None = None
    problem_frame: ProblemFrame | None = None
    gene_set: GeneSet | None = None
    optimization_snapshot: OptimizationSnapshot | None = None
    phase_change: PhaseChange | None = None
    turn_usage: TurnUsage | None = None
    background_task_started: BackgroundTaskStarted | None = None
    task_progress: TaskProgress | None = None
    task_completed: TaskCompleted | None = None


@router.get(
    "/schemas",
    response_model=StreamPartsSchemaIndex,
    include_in_schema=True,
)
async def stream_parts_schemas() -> StreamPartsSchemaIndex:
    """Stream-part payload schemas — for OpenAPI generation only."""
    return StreamPartsSchemaIndex()

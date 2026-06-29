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
from shared_py.stream_parts.enrichment import EnrichmentResultsChunk
from shared_py.stream_parts.gene_set import GeneSet
from shared_py.stream_parts.graph import (
    GraphCleared,
    GraphPlan,
    GraphSnapshot,
)
from shared_py.stream_parts.optimization import OptimizationSnapshot
from shared_py.stream_parts.phase import PhaseChange
from shared_py.stream_parts.strategy import (
    StrategyLink,
    StrategyMeta,
    StrategyPatch,
)
from shared_py.stream_parts.turn_usage import TurnUsage

from pathfinder.ai.graph.state import ConsultQuestion, UserQuestionAnswer
from pathfinder.ai.graph.stream_events import (
    ConversationTitlePayload,
    LeadUsagePayload,
    SubAgentCallPayload,
    SubAgentStepPayload,
    TurnStatusPayload,
    TurnStoppedPayload,
)
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.services.experiment.scored_comparison import ScoredComparison
from pathfinder.services.experiment.variant_comparison import VariantComparison

router = APIRouter(prefix="/api/v1/internal/stream-parts", tags=["internal"])


class StreamPartsSchemaIndex(CamelModel):
    """Index of stream-part payload schemas. Never called — exists for OpenAPI generation."""

    graph_snapshot: GraphSnapshot | None = None
    graph_plan: GraphPlan | None = None
    graph_cleared: GraphCleared | None = None
    strategy_patch: StrategyPatch | None = None
    strategy_meta: StrategyMeta | None = None
    strategy_link: StrategyLink | None = None
    consult_question: ConsultQuestion | None = None
    user_question_answer: UserQuestionAnswer | None = None
    variant_comparison: VariantComparison | None = None
    scored_comparison: ScoredComparison | None = None
    gene_set: GeneSet | None = None
    optimization_snapshot: OptimizationSnapshot | None = None
    phase_change: PhaseChange | None = None
    turn_usage: TurnUsage | None = None
    background_task_started: BackgroundTaskStarted | None = None
    task_progress: TaskProgress | None = None
    task_completed: TaskCompleted | None = None
    enrichment_results: EnrichmentResultsChunk | None = None
    sub_agent_call: SubAgentCallPayload | None = None
    sub_agent_step: SubAgentStepPayload | None = None
    turn_stopped: TurnStoppedPayload | None = None
    turn_status: TurnStatusPayload | None = None
    conversation_title: ConversationTitlePayload | None = None
    lead_usage: LeadUsagePayload | None = None


@router.get(
    "/schemas",
    response_model=StreamPartsSchemaIndex,
    include_in_schema=True,
)
async def stream_parts_schemas() -> StreamPartsSchemaIndex:
    """Stream-part payload schemas — for OpenAPI generation only."""
    return StreamPartsSchemaIndex()

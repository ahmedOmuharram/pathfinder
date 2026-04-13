"""Agent dependency building for chat turns.

Reconstructs context from Redis history, restores strategy session and plan
from the stream projection, and assembles the full ``AgentDeps`` bundle that
the pydantic-ai pipeline requires.
"""

from collections.abc import Callable
from uuid import UUID

from pydantic import ValidationError

from pathfinder.ai.agents.state import AgentToolState, SearchOverview
from pathfinder.ai.context.reconstruction import (
    extract_resume_phase_from_entries,
    reconstruct_history,
)
from pathfinder.ai.context.rendering import (
    render_approved_plan,
    render_interactive_approved_plan,
)
from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.ai.orchestration.phase_results import PhaseName, ProblemFrame
from pathfinder.domain.strategy.conversation_state import ConversationState
from pathfinder.domain.strategy.plan import PlanStatus, StrategyPlan
from pathfinder.domain.strategy.plan_payload import PersistedStrategyGraph
from pathfinder.persistence.models import StreamProjection
from pathfinder.persistence.repositories import PlanRepository, StreamRepository
from pathfinder.platform.event_schemas import PipelineConfig
from pathfinder.platform.logging import get_logger
from pathfinder.platform.redis import get_redis
from pathfinder.platform.stream_readers import (
    read_stream_entries,
    reconstruct_messages_from_entries,
)
from pathfinder.services.chat.mention_context import build_mention_context
from pathfinder.services.chat.types import ChatTurnConfig, TurnIdentity
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService
from pathfinder.services.strategies.session_factory import build_strategy_session

logger = get_logger(__name__)


def _register_plan_searches(
    agent_state: AgentToolState,
    plan: StrategyPlan,
) -> None:
    """Seed discovery state from a structured plan for execution resumption."""
    for step in plan.steps:
        if not step.search_name or agent_state.is_search_discovered(step.search_name):
            continue
        parameter_names = list(step.parameters)
        required_params = [
            name
            for name, parameter in step.parameters.items()
            if parameter.required
        ]
        agent_state.register_search(
            step.search_name,
            SearchOverview(
                search_name=step.search_name,
                display_name=step.display_name or step.search_name,
                record_type=step.record_type or "transcript",
                description=step.rationale,
                parameter_names=parameter_names,
                required_params=required_params,
            ),
        )


_RESUMABLE_PHASE_MAP: dict[str, PhaseName] = {
    "scoping": "scoping",
    "discovery": "discovery",
    "planning": "planning",
    "verification": "verification",
}

_RESUMABLE_STATUSES: frozenset[str] = frozenset(
    {"awaiting_input", "awaiting_approval"}
)


def resolve_resume_phase(
    state: ConversationState,
) -> PhaseName | None:
    """Derive the resume phase from persisted conversation state.

    Returns a phase name when the conversation was paused waiting for
    user input/approval. Returns ``None`` when no resumption is needed.
    """
    if state.current_phase is None or state.phase_status is None:
        return None
    if state.phase_status not in _RESUMABLE_STATUSES:
        return None
    return _RESUMABLE_PHASE_MAP.get(state.current_phase)


async def build_context_from_redis(
    stream_id: str,
) -> tuple[
    str | None,
    dict[str, SearchOverview],
    ProblemFrame | None,
    PhaseName | None,
]:
    """Extract context summary and discovered searches from Redis history.

    Returns ``(context_summary, discovered_searches_dict, problem_frame, resume_phase)``.
    """
    redis = get_redis()
    entries = await read_stream_entries(redis, stream_id)
    messages = reconstruct_messages_from_entries(entries)
    reconstructed = reconstruct_history(
        messages,
        recent_turn_count=3,
        resume_phase=extract_resume_phase_from_entries(entries),
    )
    return (
        reconstructed.context_summary,
        reconstructed.discovered_searches,
        reconstructed.problem_frame,
        reconstructed.resume_phase,
    )


async def build_agent_deps(
    *,
    turn: TurnIdentity,
    projection: StreamProjection,
    config: ChatTurnConfig,
    resolve_pipeline_fn: Callable[..., PipelineConfig],
    stream_repo: StreamRepository | None = None,
) -> tuple[AgentDeps, PipelineConfig]:
    """Build AgentDeps and resolve the effective pipeline.

    Returns ``(deps, effective_pipeline)``.
    """
    # Build rich context from @-mentions.
    mentioned_context: str | None = None
    if config.mentions and stream_repo is not None:
        mentioned_context = (
            await build_mention_context(config.mentions, stream_repo) or None
        )

    # Build context from Redis history.
    (
        context_summary,
        discovered_searches,
        problem_frame,
        _redis_resume_phase,
    ) = await build_context_from_redis(turn.stream_id_str)

    # Resolve resume phase from persisted conversation state (preferred)
    # with fallback to Redis-based extraction for pre-migration streams.
    conversation_state = ConversationState.model_validate(
        projection.conversation_state or {}
    )
    resume_phase = resolve_resume_phase(conversation_state) or _redis_resume_phase

    logger.debug(
        "Reconstruction: context_summary=%s discovered=%d",
        "yes" if context_summary else "no",
        len(discovered_searches),
    )

    # Resolve the effective pipeline configuration.
    effective_pipeline: PipelineConfig = resolve_pipeline_fn(
        pipeline_override=config.pipeline,
        persisted_pipeline=projection.pipeline,
    )

    # Restore the active plan from the projection.
    restored_plan: StrategyPlan | None = None
    if stream_repo is not None:
        restored_plan = await PlanRepository(stream_repo.session).get_latest_plan(
            UUID(turn.stream_id_str)
        )
    if restored_plan is None and projection.plan:
        try:
            restored_plan = StrategyPlan.model_validate(projection.plan)
        except ValidationError:
            logger.warning(
                "Failed to restore plan from projection",
                stream_id=turn.stream_id_str,
                exc_info=True,
            )

    # Reconstruct strategy session from the projection so that
    # continuation turns have full knowledge of the existing graph.
    strategy_graph_payload = PersistedStrategyGraph(
        id=turn.stream_id_str,
        name=projection.name,
        plan=projection.plan or None,
        record_type=projection.record_type,
        wdk_strategy_id=projection.wdk_strategy_id,
    )
    strategy_session = build_strategy_session(
        site_id=turn.site_id,
        strategy_graph=strategy_graph_payload,
    )

    # Build agent state with discovered searches and plan.
    agent_state = AgentToolState()
    for name, overview in discovered_searches.items():
        agent_state.register_search(name, overview)
    if restored_plan is not None:
        agent_state.set_plan(restored_plan)
        _register_plan_searches(agent_state, restored_plan)

    deps = AgentDeps(
        site_id=turn.site_id,
        user_id=turn.user_id,
        strategy_session=strategy_session,
        agent_state=agent_state,
        web_search_service=WebSearchService(),
        literature_search_service=LiteratureSearchService(),
        context_summary=context_summary,
        problem_frame=problem_frame,
        resume_phase=resume_phase,
        mentioned_context=mentioned_context,
        turn_metadata=config.metadata,
        approved_plan=(
            render_interactive_approved_plan(restored_plan)
            if (
                restored_plan is not None
                and restored_plan.status
                in (
                    PlanStatus.APPROVED,
                    PlanStatus.EXECUTING,
                    PlanStatus.COMPLETE,
                )
                and not projection.wdk_strategy_id
            )
            else (
                render_approved_plan(projection.plan)
                if projection.plan and not projection.wdk_strategy_id
                else None
            )
        ),
        plan_action=config.plan_action,
    )

    return deps, effective_pipeline

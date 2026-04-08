"""Agent dependency building for chat turns.

Reconstructs context from Redis history, restores strategy session and plan
from the stream projection, and assembles the full ``AgentDeps`` bundle that
the pydantic-ai pipeline requires.
"""

from collections.abc import Callable
from typing import cast

from pydantic import ValidationError

from pathfinder.ai.agents.state import AgentToolState, SearchOverview
from pathfinder.ai.context.reconstruction import reconstruct_history
from pathfinder.ai.context.rendering import render_approved_plan
from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.domain.strategy.plan import StrategyPlan
from pathfinder.persistence.models import StreamProjection
from pathfinder.persistence.repositories import StreamRepository
from pathfinder.platform.event_schemas import PipelineConfig
from pathfinder.platform.logging import get_logger
from pathfinder.platform.redis import get_redis
from pathfinder.platform.stream_readers import read_stream_messages
from pathfinder.platform.types import JSONObject
from pathfinder.services.chat.mention_context import build_mention_context
from pathfinder.services.chat.types import ChatTurnConfig, TurnIdentity
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService
from pathfinder.services.strategies.session_factory import build_strategy_session

logger = get_logger(__name__)


async def build_context_from_redis(
    stream_id: str,
) -> tuple[str | None, dict[str, SearchOverview]]:
    """Extract context summary and discovered searches from Redis history.

    Returns ``(context_summary, discovered_searches_dict)``.
    """
    redis = get_redis()
    messages = await read_stream_messages(redis, stream_id)
    reconstructed = reconstruct_history(messages, recent_turn_count=3)
    return (
        reconstructed.context_summary,
        reconstructed.discovered_searches,
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
    context_summary, discovered_searches = await build_context_from_redis(
        turn.stream_id_str
    )

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
    if projection.plan and isinstance(projection.plan, dict):
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
    strategy_graph_payload: JSONObject = {
        "id": turn.stream_id_str,
        "name": projection.name,
        "plan": projection.plan,
        "recordType": projection.record_type,
        "wdkStrategyId": projection.wdk_strategy_id,
    }
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

    deps = AgentDeps(
        site_id=turn.site_id,
        user_id=turn.user_id,
        strategy_session=strategy_session,
        agent_state=agent_state,
        web_search_service=WebSearchService(),
        literature_search_service=LiteratureSearchService(),
        context_summary=context_summary,
        mentioned_context=mentioned_context,
        approved_plan=(
            render_approved_plan(cast("dict[str, object]", projection.plan))
            if projection.plan and not projection.wdk_strategy_id
            else None
        ),
    )

    return deps, effective_pipeline

"""Background producer for workbench chat operations.

Runs the LLM agent in a background asyncio task and emits every
SSE event to the Redis stream for client consumption.
"""

import asyncio
from dataclasses import dataclass
from uuid import UUID

from pydantic_ai import Agent, Tool
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)

from pathfinder.ai.prompts.workbench_chat import (
    build_workbench_system_prompt,
)
from pathfinder.persistence.repositories.stream import StreamRepository
from pathfinder.persistence.session import async_session_factory
from pathfinder.platform.config import get_settings
from pathfinder.platform.errors import sanitize_error_for_client
from pathfinder.platform.events import emit
from pathfinder.platform.logging import get_logger
from pathfinder.platform.redis import get_redis
from pathfinder.platform.stream_readers import read_stream_messages
from pathfinder.platform.types import JSONObject, ModelProvider, ReasoningEffort
from pathfinder.services.experiment.ai_analysis_tools import (
    compare_gene_groups,
    fetch_result_records,
    get_attribute_distribution,
    lookup_gene_detail,
    search_results,
)
from pathfinder.services.experiment.ai_refinement_tools import (
    re_evaluate_controls,
    refine_with_gene_ids,
    refine_with_search,
)
from pathfinder.services.experiment.store import get_experiment_store
from pathfinder.services.experiment.workbench_deps import WorkbenchDeps
from pathfinder.services.workbench_chat.streaming import (
    stream_workbench_agent,
)

logger = get_logger(__name__)

# All workbench tools registered on the agent.
WORKBENCH_TOOLS: list[Tool[WorkbenchDeps]] = [
    Tool(fetch_result_records),
    Tool(lookup_gene_detail),
    Tool(get_attribute_distribution),
    Tool(compare_gene_groups),
    Tool(search_results),
    Tool(refine_with_search),
    Tool(refine_with_gene_ids),
    Tool(re_evaluate_controls),
]


@dataclass
class WorkbenchTurnConfig:
    """Per-turn model configuration for a workbench chat operation."""

    provider_override: ModelProvider | None = None
    model_override: str | None = None
    reasoning_effort: ReasoningEffort | None = None


@dataclass
class WorkbenchProducerIds:
    """Immutable stream/operation/site identifiers for the background producer."""

    stream_id_str: str
    operation_id: str
    site_id: str
    experiment_id: str
    user_id: UUID


def resolve_model_id(
    model_override: str | None = None,
) -> str:
    """Resolve the effective model ID from overrides or settings default.

    Falls back to the execution-phase model from the default tier preset,
    since workbench chat is closest to execution-style work.
    """
    if model_override:
        return model_override
    settings = get_settings()
    from pathfinder.ai.models.tiers import get_tier_preset  # noqa: PLC0415

    preset = get_tier_preset(settings.default_provider, settings.default_tier)
    if preset is not None:
        return preset.execution.model_id
    return f"{settings.default_provider}/default"


async def build_chat_history_from_redis(
    stream_id_str: str,
) -> list[ModelMessage]:
    """Build pydantic-ai-compatible chat history from Redis stream events.

    Excludes the last message (the one just emitted for the current turn).
    """
    redis = get_redis()
    messages = await read_stream_messages(redis, stream_id_str)
    history: list[ModelMessage] = []
    for msg in messages[:-1]:  # exclude the message we just emitted
        role = msg.get("role")
        content = str(msg.get("content", ""))
        if not content:
            continue
        if role == "user":
            history.append(
                ModelRequest(parts=[UserPromptPart(content=content)])
            )
        elif role == "assistant":
            history.append(
                ModelResponse(parts=[TextPart(content=content)])
            )
    return history


async def workbench_chat_producer(
    *,
    ids: WorkbenchProducerIds,
    message: str,
    config: WorkbenchTurnConfig,
) -> None:
    """Background task: run the workbench LLM agent and emit every event to Redis."""
    redis = get_redis()

    async with async_session_factory() as session:
        bg_stream_repo = StreamRepository(session)

        # Build chat history from Redis (not from DB).
        chat_history = await build_chat_history_from_redis(ids.stream_id_str)

        # Build experiment context for prompt.
        store = get_experiment_store()
        exp = await store.aget(ids.experiment_id)
        experiment_context: JSONObject = {}
        if exp:
            experiment_context["experimentId"] = exp.id
            experiment_context["status"] = exp.status
            if exp.metrics:
                experiment_context["metrics"] = exp.metrics.model_dump(by_alias=True)
            if exp.config:
                experiment_context["config"] = exp.config.model_dump(by_alias=True)

        system_prompt = build_workbench_system_prompt(
            site_id=ids.site_id,
            experiment_context=experiment_context,
        )

        effective_model = resolve_model_id(
            model_override=config.model_override,
        )

        # Build a pydantic-ai Agent inline for this workbench turn.
        agent: Agent[WorkbenchDeps, str] = Agent(
            effective_model,
            deps_type=WorkbenchDeps,
            system_prompt=system_prompt,
            tools=WORKBENCH_TOOLS,
        )

        deps = WorkbenchDeps(
            site_id=ids.site_id,
            experiment_id=ids.experiment_id,
            user_id=ids.user_id,
        )

        stream_iter = stream_workbench_agent(
            agent, message, deps, chat_history, effective_model,
            tool_count=len(WORKBENCH_TOOLS),
        )

        try:
            await emit(
                redis,
                ids.stream_id_str,
                ids.operation_id,
                "message_start",
                {"experimentId": ids.experiment_id},
                session=session,
            )

            async for event_value in stream_iter:
                if not isinstance(event_value, dict):
                    continue
                event_type_raw = event_value.get("type", "")
                event_type = event_type_raw if isinstance(event_type_raw, str) else ""
                event_data_raw = event_value.get("data")
                event_data = event_data_raw if isinstance(event_data_raw, dict) else {}

                await emit(
                    redis,
                    ids.stream_id_str,
                    ids.operation_id,
                    event_type,
                    event_data,
                    session=session,
                )

            await bg_stream_repo.complete_operation(ids.operation_id)

        except asyncio.CancelledError:
            logger.info(
                "Workbench chat producer cancelled", operation_id=ids.operation_id
            )
            await emit(
                redis,
                ids.stream_id_str,
                ids.operation_id,
                "message_end",
                {},
                session=session,
            )
            await bg_stream_repo.cancel_operation(ids.operation_id)
            await session.commit()
            return

        except Exception as e:
            logger.error(
                "Workbench chat producer error",
                error=str(e),
                exc_info=True,
            )
            await emit(
                redis,
                ids.stream_id_str,
                ids.operation_id,
                "error",
                {"error": sanitize_error_for_client(e)},
                session=session,
            )
            await emit(
                redis,
                ids.stream_id_str,
                ids.operation_id,
                "message_end",
                {},
                session=session,
            )
            await bg_stream_repo.fail_operation(ids.operation_id)

        await session.commit()

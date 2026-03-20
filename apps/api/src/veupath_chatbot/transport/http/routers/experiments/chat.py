"""Workbench chat endpoints - conversational AI per experiment."""

from fastapi import APIRouter

from veupath_chatbot.platform.events import read_stream_messages
from veupath_chatbot.platform.redis import get_redis
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.workbench_chat.orchestrator import (
    start_workbench_chat_stream,
)
from veupath_chatbot.transport.http.deps import CurrentUser, StreamRepo, UserRepo
from veupath_chatbot.transport.http.schemas.workbench_chat import (
    WorkbenchChatRequest,
    WorkbenchChatResponse,
)

router = APIRouter()


@router.post("/{experiment_id}/chat", status_code=202)
async def workbench_chat(
    experiment_id: str,
    body: WorkbenchChatRequest,
    user_repo: UserRepo,
    stream_repo: StreamRepo,
    user_id: CurrentUser,
) -> WorkbenchChatResponse:
    """Start a conversational AI chat for an experiment.

    Returns operation ID for SSE subscription via
    GET /operations/{operationId}/subscribe.
    """
    op_id, stream_id = await start_workbench_chat_stream(
        message=body.message,
        site_id=body.site_id,
        experiment_id=experiment_id,
        user_id=user_id,
        user_repo=user_repo,
        stream_repo=stream_repo,
        provider_override=body.provider,
        model_override=body.model_id,
        reasoning_effort=body.reasoning_effort,
    )
    return WorkbenchChatResponse(operationId=op_id, streamId=stream_id)


@router.get("/{experiment_id}/chat/messages")
async def get_workbench_chat_messages(
    experiment_id: str,
    user_id: CurrentUser,
    stream_repo: StreamRepo,
    user_repo: UserRepo,
) -> list[JSONObject]:
    """Get conversation history for an experiment's chat."""
    user = await user_repo.get_or_create(user_id)
    stream = await stream_repo.find_by_experiment(user.id, experiment_id)
    if stream is None:
        return []

    redis = get_redis()
    return await read_stream_messages(redis, str(stream.id))

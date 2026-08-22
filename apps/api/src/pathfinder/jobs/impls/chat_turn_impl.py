from __future__ import annotations

from contextlib import nullcontext
from typing import Any

from pathfinder.ai.conversation.turn_runner import run_turn
from pathfinder.ai.graph._llm_capture import capture_llm
from pathfinder.ai.graph.composition import build_pathfinder_graph
from pathfinder.assistant_core.conversation.checkpointer import lifespan_checkpointer
from pathfinder.assistant_core.conversation.event_writer import ChatEventWriter
from pathfinder.assistant_core.memory.lifespan import lifespan_memory_store
from pathfinder.jobs.auth_context import (
    attach_conversation_application,
    attach_user_id,
    attach_wdk_auth,
)
from pathfinder.jobs.payloads import ChatTurnPayload
from pathfinder.platform.config import get_settings
from pathfinder.platform.logging import get_logger

logger = get_logger(__name__)


async def run_chat_turn(payload: dict[str, Any]) -> None:
    """Procrastinate job body — drives one chat turn through the worker.

    Payload crosses a process boundary (api → worker) so we re-install the
    user's VEuPathDB auth cookie on ``veupathdb_auth_token_ctx`` for the
    duration of the turn. Without this, every WDK call from the agent
    would fall through to the service-account token in settings.
    """
    parsed = ChatTurnPayload.model_validate(payload)
    body = parsed.body

    writer = ChatEventWriter(
        conversation_id=body.conversation_id,
        turn_id=parsed.turn_id,
    )
    settings = get_settings()
    async with (
        attach_wdk_auth(parsed.veupathdb_auth_token),
        attach_user_id(parsed.user_id),
        attach_conversation_application(body.conversation_id),
        lifespan_checkpointer(settings.database_url) as saver,
        lifespan_memory_store(settings.database_url) as store,
    ):
        graph = build_pathfinder_graph(checkpointer=saver)
        capture = (
            capture_llm(parsed.capture_dir) if parsed.capture_dir else nullcontext()
        )
        with capture:
            await run_turn(
                body=body,
                user_id=parsed.user_id,
                compiled_graph=graph,
                memory_store=store,
                writer=writer,
            )
    logger.info(
        "chat turn completed",
        conversation_id=str(body.conversation_id),
        turn_id=str(parsed.turn_id),
        has_veupathdb_auth=parsed.veupathdb_auth_token is not None,
    )

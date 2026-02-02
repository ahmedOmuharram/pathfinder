"""Chat orchestration entrypoint (service layer).

Implementation details are split across smaller modules. The HTTP layer should
call `start_chat_stream` and remain thin.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID

from veupath_chatbot.ai.agent_factory import create_agent
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.security import create_user_token
from veupath_chatbot.persistence.repo import StrategyRepository, UserRepository
from veupath_chatbot.transport.http.streaming import stream_chat

from veupath_chatbot.services.chat.bootstrap import (
    append_user_message,
    build_chat_history,
    build_strategy_payload,
    ensure_strategy,
    ensure_user,
)
from veupath_chatbot.services.chat.processor import ChatStreamProcessor
from veupath_chatbot.services.chat.utils import parse_selected_nodes

logger = get_logger(__name__)


async def start_chat_stream(
    *,
    message: str,
    site_id: str,
    strategy_id: UUID | None,
    user_id: UUID | None,
    user_repo: UserRepository,
    strategy_repo: StrategyRepository,
) -> tuple[str, AsyncIterator[str]]:
    """Start an SSE stream for a chat turn.

    Returns `(auth_token, sse_iterator)` where `sse_iterator` yields SSE-formatted strings.
    """
    user_id = await ensure_user(user_repo, user_id)
    auth_token = create_user_token(user_id)

    strategy = await ensure_strategy(
        strategy_repo,
        user_id=user_id,
        site_id=site_id,
        strategy_id=strategy_id,
    )

    await append_user_message(strategy_repo, strategy_id=strategy.id, message=message)
    selected_nodes, model_message = parse_selected_nodes(message)

    history = await build_chat_history(strategy_repo, strategy=strategy)
    strategy_payload = build_strategy_payload(strategy)

    strategy_graph_payload = {"id": strategy.id, "name": strategy.name, "plan": strategy.plan}

    agent = create_agent(
        site_id=site_id,
        user_id=user_id,
        chat_history=history,
        strategy_graph=strategy_graph_payload,
        selected_nodes=selected_nodes,
    )

    async def event_generator() -> AsyncIterator[str]:
        processor = ChatStreamProcessor(
            strategy_repo=strategy_repo,
            site_id=site_id,
            user_id=user_id,
            strategy=strategy,
            auth_token=auth_token,
            strategy_payload=strategy_payload,
        )
        try:
            yield processor.start_event()

            async for event in stream_chat(agent, model_message):
                event_type = event.get("type", "")
                event_data = event.get("data", {}) or {}
                sse_line = await processor.on_event(event_type, event_data)
                if sse_line:
                    yield sse_line

            for extra in await processor.finalize():
                yield extra
        except Exception as e:
            yield await processor.handle_exception(e)

    return auth_token, event_generator()


"""Bootstrap helpers for starting a chat turn."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

from kani import ChatMessage, ChatRole
from kani.models import FunctionCall, ToolCall

from veupath_chatbot.persistence.models import Strategy
from veupath_chatbot.persistence.repo import StrategyRepository
from veupath_chatbot.platform.errors import ErrorCode, NotFoundError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONArray, JSONObject, as_json_object
from veupath_chatbot.services.chat.thinking import normalize_tool_calls

from .utils import parse_selected_nodes

logger = get_logger(__name__)


async def ensure_strategy(
    strategy_repo: StrategyRepository,
    *,
    user_id: UUID,
    site_id: str,
    strategy_id: UUID | None,
) -> Strategy:
    if strategy_id:
        strategy = await strategy_repo.get_by_id(strategy_id)
        if not strategy:
            logger.warning(
                "Strategy not found; creating new",
                strategy_id=strategy_id,
            )
            strategy = await strategy_repo.create(
                user_id=user_id,
                name="Draft Strategy",
                title="Draft Strategy",
                site_id=site_id,
                record_type=None,
                plan={},
                strategy_id=strategy_id,
            )
    else:
        strategy = await strategy_repo.create(
            user_id=user_id,
            name="Draft Strategy",
            title="Draft Strategy",
            site_id=site_id,
            record_type=None,
            plan={},
        )
    if not strategy:
        raise NotFoundError(
            code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
        )
    return strategy


async def append_user_message(
    strategy_repo: StrategyRepository, *, strategy_id: UUID, message: str
) -> None:
    user_message: JSONObject = {
        "role": "user",
        "content": message,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    await strategy_repo.add_message(strategy_id, user_message)
    await strategy_repo.clear_thinking(strategy_id)


async def build_chat_history(
    strategy_repo: StrategyRepository, *, strategy: Strategy
) -> list[ChatMessage]:
    history: list[ChatMessage] = []
    await strategy_repo.refresh(strategy)
    for msg_value in strategy.messages or []:
        if not isinstance(msg_value, dict):
            continue
        msg = as_json_object(msg_value)
        role_value = msg.get("role")
        content_value = msg.get("content")
        if not content_value:
            continue
        content = str(content_value) if content_value is not None else ""
        if role_value == "user":
            _, cleaned = parse_selected_nodes(content)
            history.append(ChatMessage(role=ChatRole.USER, content=cleaned))
        elif role_value == "assistant":
            history.append(ChatMessage(role=ChatRole.ASSISTANT, content=content))
    return history


def build_plan_chat_history(*, messages: JSONArray) -> list[ChatMessage]:
    """Build chat history for the planner including tool calls and their results.

    :param messages: Message list.

    """
    history: list[ChatMessage] = []
    for msg_value in messages or []:
        if not isinstance(msg_value, dict):
            continue
        msg = as_json_object(msg_value)
        role_raw = msg.get("role")
        content_raw = msg.get("content")
        if role_raw == "user":
            content = str(content_raw) if content_raw is not None else ""
            _, cleaned = parse_selected_nodes(content)
            history.append(ChatMessage(role=ChatRole.USER, content=cleaned))
            continue
        if role_raw != "assistant":
            continue

        content = str(content_raw) if content_raw is not None else ""
        tool_calls_raw = msg.get("toolCalls")
        tool_calls_list: JSONArray = []
        if isinstance(tool_calls_raw, list) and tool_calls_raw:
            tool_calls_list = normalize_tool_calls(tool_calls_raw)

        if tool_calls_list:
            kani_tool_calls: list[ToolCall] = []
            for tc in tool_calls_list:
                if not isinstance(tc, dict):
                    continue
                name = tc.get("name")
                args = tc.get("arguments")
                if not name:
                    continue
                if isinstance(args, str):
                    args_str = args
                elif isinstance(args, dict):
                    args_str = json.dumps(args)
                else:
                    args_str = "{}"
                call_id = str(tc.get("id") or "")
                if not call_id:
                    continue
                kani_tool_calls.append(
                    ToolCall(
                        id=call_id,
                        type="function",
                        function=FunctionCall(name=name, arguments=args_str),
                    )
                )
            history.append(
                ChatMessage(
                    role=ChatRole.ASSISTANT,
                    content=content or None,
                    tool_calls=kani_tool_calls,
                )
            )
            for tc in tool_calls_list:
                if not isinstance(tc, dict):
                    continue
                result = tc.get("result")
                name = tc.get("name")
                call_id = str(tc.get("id") or "")
                if not call_id:
                    continue
                if isinstance(result, str):
                    result_str = result
                elif result is not None:
                    result_str = json.dumps(result)
                else:
                    result_str = ""
                history.append(
                    ChatMessage.function(
                        name=name or "",
                        content=result_str,
                        tool_call_id=call_id,
                    )
                )
        else:
            history.append(ChatMessage(role=ChatRole.ASSISTANT, content=content))
    return history


def build_strategy_payload(strategy: Strategy) -> JSONObject:
    strategy_data = strategy.__dict__
    updated_at = strategy_data.get("updated_at") or strategy_data.get("created_at")
    return {
        "id": str(strategy.id),
        "name": strategy.name,
        "siteId": strategy.site_id,
        "recordType": strategy.record_type,
        "updatedAt": updated_at.isoformat() if updated_at else None,
        "wdkStrategyId": strategy.wdk_strategy_id,
    }

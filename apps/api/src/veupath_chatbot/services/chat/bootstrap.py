"""Bootstrap helpers for starting a chat turn."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from kani import ChatMessage, ChatRole

from veupath_chatbot.platform.errors import ErrorCode, NotFoundError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.persistence.models import Strategy, User
from veupath_chatbot.persistence.repo import StrategyRepository, UserRepository

from .utils import parse_selected_nodes

logger = get_logger(__name__)


async def ensure_user(user_repo: UserRepository, user_id: UUID | None) -> UUID:
    if user_id:
        await user_repo.get_or_create(user_id)
        return user_id
    user: User = await user_repo.create()
    return user.id


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
                steps=[],
                root_step_id=None,
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
            steps=[],
            root_step_id=None,
        )
    if not strategy:
        raise NotFoundError(code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found")
    return strategy


async def append_user_message(
    strategy_repo: StrategyRepository, *, strategy_id: UUID, message: str
) -> None:
    user_message = {
        "role": "user",
        "content": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await strategy_repo.add_message(strategy_id, user_message)
    await strategy_repo.clear_thinking(strategy_id)


async def build_chat_history(
    strategy_repo: StrategyRepository, *, strategy: Strategy
) -> list[ChatMessage]:
    history: list[ChatMessage] = []
    await strategy_repo.refresh(strategy)
    for msg in strategy.messages or []:
        role = msg.get("role")
        content = msg.get("content")
        if not content:
            continue
        if role == "user":
            _, cleaned = parse_selected_nodes(content)
            history.append(ChatMessage(role=ChatRole.USER, content=cleaned))
        elif role == "assistant":
            history.append(ChatMessage(role=ChatRole.ASSISTANT, content=content))
    return history


def build_strategy_payload(strategy: Strategy) -> dict[str, Any]:
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


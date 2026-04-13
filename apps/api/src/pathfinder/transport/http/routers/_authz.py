"""Shared router helpers for resource lookup and authorization."""

from uuid import UUID

from pathfinder.persistence.models import Chat
from pathfinder.persistence.repositories import ChatRepository
from pathfinder.platform.errors import ErrorCode, ForbiddenError, NotFoundError


async def get_chat_or_404(chat_repo: ChatRepository, chat_id: UUID) -> Chat:
    chat = await chat_repo.get_by_id(chat_id)
    if not chat:
        raise NotFoundError(
            code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
        )
    return chat


async def get_owned_chat_or_404(
    chat_repo: ChatRepository, chat_id: UUID, user_id: UUID
) -> Chat:
    chat = await get_chat_or_404(chat_repo, chat_id)
    if chat.user_id != user_id:
        raise ForbiddenError
    return chat

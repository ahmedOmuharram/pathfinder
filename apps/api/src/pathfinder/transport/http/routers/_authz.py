"""Shared router helpers for resource lookup and authorization."""

from uuid import UUID

from pathfinder.persistence.models import Conversation
from pathfinder.persistence.repositories import ConversationRepository
from pathfinder.platform.errors import ErrorCode, ForbiddenError, NotFoundError


async def get_chat_or_404(conv_repo: ConversationRepository, conversation_id: UUID) -> Conversation:
    conversation = await conv_repo.get_by_id(conversation_id)
    if not conversation:
        raise NotFoundError(
            code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
        )
    return conversation


async def get_owned_conversation_or_404(
    conv_repo: ConversationRepository, conversation_id: UUID, user_id: UUID
) -> Conversation:
    conversation = await get_chat_or_404(conv_repo, conversation_id)
    if conversation.user_id != user_id:
        raise ForbiddenError
    return conversation

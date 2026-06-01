"""Conversation lookup + ownership authorization (service-internal)."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.persistence.models import Conversation
from pathfinder.persistence.repositories import ConversationRepository
from pathfinder.platform.errors import ErrorCode, ForbiddenError, NotFoundError


async def get_chat_or_404(
    conv_repo: ConversationRepository,
    conversation_id: UUID,
) -> Conversation:
    conversation = await conv_repo.get_by_id(conversation_id)
    if not conversation:
        raise NotFoundError(
            code=ErrorCode.STRATEGY_NOT_FOUND,
            title="Strategy not found",
        )
    return conversation


async def get_owned_conversation_or_404(
    conv_repo: ConversationRepository,
    conversation_id: UUID,
    user_id: UUID,
) -> Conversation:
    conversation = await get_chat_or_404(conv_repo, conversation_id)
    if conversation.user_id != user_id:
        raise ForbiddenError
    return conversation


async def get_owned_or_404(
    conv_repo: ConversationRepository,
    conversation_id: UUID,
    user_id: UUID,
) -> Conversation:
    """Return the conversation, raising 404 for missing **or** wrong-owner.

    Unlike :func:`get_owned_conversation_or_404` (which 403s a wrong owner),
    this hides existence from non-owners — the behaviour the scratchpad,
    events, cancel and sidebar endpoints have always had.
    """
    conv = await conv_repo.get_by_id(conversation_id)
    if conv is None or conv.user_id != user_id:
        raise NotFoundError(
            code=ErrorCode.STRATEGY_NOT_FOUND,
            title="conversation not found",
        )
    return conv


async def assert_owner(
    session: AsyncSession,
    conversation_id: UUID,
    user_id: UUID,
) -> None:
    """Raise 404 unless ``user_id`` owns ``conversation_id`` (hides existence)."""
    await get_owned_or_404(
        ConversationRepository(session),
        conversation_id,
        user_id,
    )

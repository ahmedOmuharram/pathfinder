"""Conversation lookup + ownership authorization (service-internal).

A conversation belongs to a user under one application, so both must match
before a caller reaches it.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.persistence.models import Conversation
from pathfinder.persistence.repositories import ConversationRepository
from pathfinder.platform.context import calling_application
from pathfinder.platform.db import async_session_factory
from pathfinder.platform.errors import ErrorCode, ForbiddenError, NotFoundError


def owned_by_caller(conversation: Conversation, user_id: UUID) -> bool:
    """Whether the conversation belongs to this user under this application."""
    return (
        conversation.user_id == user_id
        and conversation.application_id == calling_application()
    )


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
    if not owned_by_caller(conversation, user_id):
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
    if conv is None or not owned_by_caller(conv, user_id):
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


async def conversation_application_id(conversation_id: UUID) -> str | None:
    """Return the application that holds a conversation, or None if it is gone.

    The row is the source of truth a worker job reads to run as the right
    application.
    """
    async with async_session_factory() as session:
        application_id: str | None = await session.scalar(
            select(Conversation.application_id).where(
                Conversation.id == conversation_id,
            ),
        )
    return application_id

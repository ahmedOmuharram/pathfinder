"""Dependency injection for HTTP routes."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from veupath_chatbot.persistence.repositories import (
    ControlSetRepository,
    StreamRepository,
    UserRepository,
)
from veupath_chatbot.persistence.session import get_db_session
from veupath_chatbot.platform.errors import ForbiddenError, NotFoundError
from veupath_chatbot.platform.security import get_current_user
from veupath_chatbot.services.experiment.store import get_experiment_store
from veupath_chatbot.services.experiment.types import Experiment

# Type aliases for dependencies
DBSession = Annotated[AsyncSession, Depends(get_db_session)]


async def get_user_repo(session: DBSession) -> UserRepository:
    """Get user repository."""
    return UserRepository(session)


async def get_control_set_repo(session: DBSession) -> ControlSetRepository:
    """Get control set repository."""
    return ControlSetRepository(session)


async def get_stream_repo(session: DBSession) -> StreamRepository:
    """Get stream repository."""
    return StreamRepository(session)


UserRepo = Annotated[UserRepository, Depends(get_user_repo)]
ControlSetRepo = Annotated[ControlSetRepository, Depends(get_control_set_repo)]
StreamRepo = Annotated[StreamRepository, Depends(get_stream_repo)]


async def get_current_user_with_db_row(
    user_id: Annotated[UUID, Depends(get_current_user)],
    user_repo: UserRepo,
) -> UUID:
    """Ensure authenticated users exist in the local DB.

    We persist user IDs because many tables have a FK to `users.id`. Without this,
    first-time sessions can trigger integrity errors that bubble up as 500s.
    """
    await user_repo.get_or_create(user_id)
    return user_id


CurrentUser = Annotated[UUID, Depends(get_current_user_with_db_row)]


async def get_experiment_owned_by_user(
    experiment_id: str,
    user_id: CurrentUser,
) -> Experiment:
    """Resolve an experiment by ID and verify the current user owns it."""
    store = get_experiment_store()
    exp = await store.aget(experiment_id)
    if not exp:
        raise NotFoundError(title="Experiment not found")
    if exp.user_id != str(user_id):
        raise ForbiddenError(title="Not authorized to access this experiment")
    return exp


ExperimentDep = Annotated[Experiment, Depends(get_experiment_owned_by_user)]

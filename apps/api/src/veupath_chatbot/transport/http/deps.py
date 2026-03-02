"""Dependency injection for HTTP routes."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from veupath_chatbot.integrations.veupathdb.factory import SiteInfo, get_site
from veupath_chatbot.persistence.repo import (
    ControlSetRepository,
    StrategyRepository,
    UserRepository,
)
from veupath_chatbot.persistence.session import get_db_session
from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.context import site_id_ctx
from veupath_chatbot.platform.errors import NotFoundError
from veupath_chatbot.platform.security import get_current_user, get_optional_user
from veupath_chatbot.services.experiment.store import get_experiment_store
from veupath_chatbot.services.experiment.types import Experiment

# Type aliases for dependencies
DBSession = Annotated[AsyncSession, Depends(get_db_session)]
OptionalUser = Annotated[UUID | None, Depends(get_optional_user)]


async def get_user_repo(session: DBSession) -> UserRepository:
    """Get user repository."""
    return UserRepository(session)


async def get_strategy_repo(session: DBSession) -> StrategyRepository:
    """Get strategy repository."""
    return StrategyRepository(session)


async def get_control_set_repo(session: DBSession) -> ControlSetRepository:
    """Get control set repository."""
    return ControlSetRepository(session)


UserRepo = Annotated[UserRepository, Depends(get_user_repo)]
StrategyRepo = Annotated[StrategyRepository, Depends(get_strategy_repo)]
ControlSetRepo = Annotated[ControlSetRepository, Depends(get_control_set_repo)]


async def get_experiment_or_404(experiment_id: str) -> Experiment:
    """Resolve an experiment by ID or raise 404."""
    store = get_experiment_store()
    exp = await store.aget(experiment_id)
    if not exp:
        raise NotFoundError(title="Experiment not found")
    return exp


ExperimentDep = Annotated[Experiment, Depends(get_experiment_or_404)]


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


async def get_site_context(
    site_id: Annotated[
        str | None,
        Query(description="VEuPathDB site ID"),
    ] = None,
    x_site_id: Annotated[
        str | None,
        Header(description="VEuPathDB site ID (header)"),
    ] = None,
) -> SiteInfo:
    """Get site context from query or header.

    Priority: query param > header > default
    """
    settings = get_settings()

    effective_site_id = site_id or x_site_id or settings.veupathdb_default_site
    site = get_site(effective_site_id)

    # Set context var
    site_id_ctx.set(site.id)

    return site


SiteContext = Annotated[SiteInfo, Depends(get_site_context)]

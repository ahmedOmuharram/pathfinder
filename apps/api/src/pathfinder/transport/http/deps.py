"""Dependency injection for HTTP routes."""

import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.persistence.repositories import (
    ChatRepository,
    ControlSetRepository,
    UserRepository,
)
from pathfinder.persistence.repositories.checkpoint_label import (
    CheckpointLabelRepository,
)
from pathfinder.persistence.session import async_session_factory, get_db_session
from pathfinder.platform.errors import ForbiddenError, NotFoundError
from pathfinder.platform.security import get_current_user
from pathfinder.services.checkpoints import CheckpointService, GraphLike
from pathfinder.services.experiment.store import get_experiment_store
from pathfinder.services.experiment.types import Experiment

# Type aliases for dependencies
DBSession = Annotated[AsyncSession, Depends(get_db_session)]


async def get_user_repo(session: DBSession) -> UserRepository:
    """Get user repository."""
    return UserRepository(session)


async def get_control_set_repo(session: DBSession) -> ControlSetRepository:
    """Get control set repository."""
    return ControlSetRepository(session)


async def get_chat_repo(session: DBSession) -> ChatRepository:
    """Get chat repository."""
    return ChatRepository(session)


UserRepo = Annotated[UserRepository, Depends(get_user_repo)]
ControlSetRepo = Annotated[ControlSetRepository, Depends(get_control_set_repo)]
ChatRepo = Annotated[ChatRepository, Depends(get_chat_repo)]


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


async def get_experiments_owned_by_user(
    experiment_ids: list[str], user_id: str
) -> list[Experiment]:
    """Fetch multiple experiments by ID and verify ownership (parallel)."""
    store = get_experiment_store()
    fetched = await asyncio.gather(*(store.aget(eid) for eid in experiment_ids))
    experiments: list[Experiment] = []
    for eid, exp in zip(experiment_ids, fetched, strict=True):
        if not exp:
            raise NotFoundError(title=f"Experiment {eid} not found")
        if exp.user_id != user_id:
            raise ForbiddenError(title="Not authorized to access this experiment")
        experiments.append(exp)
    return experiments


def get_checkpoint_label_repo() -> CheckpointLabelRepository:
    """Sidecar repository for per-user checkpoint labels."""
    return CheckpointLabelRepository(session_factory=async_session_factory)


def get_checkpoint_service(request: Request) -> CheckpointService:
    """Build a ``CheckpointService`` against the app's compiled graph.

    The service's ``graph_factory`` returns the already-compiled graph that
    was wired with the long-lived ``AsyncPostgresSaver`` during the
    application lifespan. Reusing the compiled graph avoids re-creating
    psycopg connections on every checkpoint request.
    """
    compiled_graph: GraphLike = request.app.state.compiled_graph

    def _factory() -> GraphLike:
        return compiled_graph

    return CheckpointService(
        session_factory=async_session_factory,
        graph_factory=_factory,
    )

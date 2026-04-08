"""Shared router helpers for resource lookup and authorization."""

from uuid import UUID

from pathfinder.persistence.models import StreamProjection
from pathfinder.persistence.repositories.stream import StreamRepository
from pathfinder.platform.errors import ErrorCode, ForbiddenError, NotFoundError


async def get_projection_or_404(
    stream_repo: StreamRepository, stream_id: UUID
) -> StreamProjection:
    projection = await stream_repo.get_projection(stream_id)
    if not projection:
        raise NotFoundError(
            code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
        )
    return projection


async def get_owned_projection_or_404(
    stream_repo: StreamRepository, stream_id: UUID, user_id: UUID
) -> StreamProjection:
    projection = await get_projection_or_404(stream_repo, stream_id)
    if not projection.stream or projection.stream.user_id != user_id:
        raise ForbiddenError
    return projection

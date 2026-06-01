import asyncio
from typing import Protocol, runtime_checkable

from pathfinder.platform.errors import AppError
from pathfinder.platform.logging import get_logger

logger = get_logger(__name__)


@runtime_checkable
class StepDeleteAPI(Protocol):
    async def delete_step(
        self, step_id: int, *, user_id: str | None = None
    ) -> None: ...


async def delete_orphaned_wdk_steps(
    api: StepDeleteAPI,
    wdk_step_ids: list[int],
) -> list[int]:
    """Delete orphaned WDK step rows in parallel. Returns ids that failed.

    Tolerates per-step failures: a transient DELETE failure should not abort
    the surrounding commit pipeline. The caller decides how to surface
    leftovers.
    """
    if not wdk_step_ids:
        return []

    async def _one(step_id: int) -> int | None:
        try:
            await api.delete_step(step_id)
        except AppError as exc:
            logger.warning(
                "Failed to delete orphaned WDK step",
                step_id=step_id,
                error=str(exc),
            )
            return step_id
        return None

    results = await asyncio.gather(*(_one(sid) for sid in wdk_step_ids))
    return [sid for sid in results if sid is not None]

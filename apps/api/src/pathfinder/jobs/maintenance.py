"""Release the per-conversation lock a killed worker leaves behind."""

from __future__ import annotations

import warnings

from procrastinate.jobs import Status

from pathfinder.jobs.app import procrastinate_app
from pathfinder.platform.config import get_settings
from pathfinder.platform.logging import get_logger

logger = get_logger(__name__)


async def release_stalled_jobs() -> None:
    """Fail every job left in ``doing`` past the timeout, without retrying it.

    Staleness is the age of the job's started event, not the worker heartbeat,
    because a busy worker can miss heartbeats while its job is alive.
    """
    manager = procrastinate_app.job_manager
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        stalled = await manager.get_stalled_jobs(
            nb_seconds=get_settings().worker_stalled_job_timeout_seconds,
        )
    for job in stalled:
        await manager.finish_job(job, status=Status.FAILED, delete_job=False)
        logger.warning(
            "Released a stalled job",
            job_id=job.id,
            task_name=job.task_name,
            queue_name=job.queue,
            lock=job.lock,
        )

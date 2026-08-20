"""A job stuck in ``doing`` is failed so its per-conversation lock releases."""

from __future__ import annotations

import datetime
from typing import Any

import pytest
from procrastinate.testing import InMemoryConnector

from pathfinder.jobs.app import procrastinate_app
from pathfinder.jobs.maintenance import release_stalled_jobs
from pathfinder.jobs.tasks import ensure_registered
from pathfinder.platform.config import Settings, get_settings

_TASK_NAME = "maintenance:release_stalled_jobs"
_LOCK = "8f14e45f-ceea-467a-9e58-2b1c9d3e4a5b"


async def _defer_locked_turn(connector: InMemoryConnector, lock: str) -> int:
    from pathfinder.jobs.tasks import run_chat_turn_job  # noqa: PLC0415

    del connector
    return await run_chat_turn_job.configure(lock=lock).defer_async(payload={})


async def _start_job(connector: InMemoryConnector, job_id: int) -> None:
    connector.jobs[job_id]["status"] = "doing"
    connector.events[job_id].append(
        {"type": "started", "at": datetime.datetime.now(tz=datetime.UTC)},
    )


def _age_last_event(
    connector: InMemoryConnector,
    job_id: int,
    seconds: int,
) -> None:
    events = connector.events[job_id]
    events[-1]["at"] = datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(
        seconds=seconds,
    )


async def _fetch_one(connector: InMemoryConnector) -> dict[str, Any]:
    worker = await connector.register_worker_one()
    return await connector.fetch_job_one(queues=None, worker_id=worker["worker_id"])


async def test_a_stalled_job_is_failed_and_frees_its_lock(
    in_memory_jobs: InMemoryConnector,
) -> None:
    stalled_id = await _defer_locked_turn(in_memory_jobs, _LOCK)
    await _start_job(in_memory_jobs, stalled_id)
    _age_last_event(in_memory_jobs, stalled_id, seconds=7200)
    waiting_id = await _defer_locked_turn(in_memory_jobs, _LOCK)

    assert (await _fetch_one(in_memory_jobs))["id"] is None

    await release_stalled_jobs()

    assert in_memory_jobs.jobs[stalled_id]["status"] == "failed"
    assert (await _fetch_one(in_memory_jobs))["id"] == waiting_id


async def test_a_young_doing_job_is_left_alone(
    in_memory_jobs: InMemoryConnector,
) -> None:
    running_id = await _defer_locked_turn(in_memory_jobs, _LOCK)
    await _start_job(in_memory_jobs, running_id)
    _age_last_event(in_memory_jobs, running_id, seconds=60)

    await release_stalled_jobs()

    assert in_memory_jobs.jobs[running_id]["status"] == "doing"


class TestStalledTimeoutSetting:
    def test_it_defaults_to_one_hour(self) -> None:
        get_settings.cache_clear()
        assert get_settings().worker_stalled_job_timeout_seconds == 3600

    def test_it_rejects_a_value_below_the_floor(self) -> None:
        with pytest.raises(ValueError, match="worker_stalled_job_timeout_seconds"):
            Settings(worker_stalled_job_timeout_seconds=299)


class TestPeriodicRegistration:
    def test_the_sweep_runs_every_minute_on_the_maintenance_queue(self) -> None:
        ensure_registered()
        task = procrastinate_app.tasks[_TASK_NAME]
        assert task.queue == "maintenance"
        registered = [
            periodic
            for periodic in procrastinate_app.periodic_registry.periodic_tasks.values()
            if periodic.task.name == _TASK_NAME
        ]
        assert len(registered) == 1
        assert registered[0].cron == "* * * * *"

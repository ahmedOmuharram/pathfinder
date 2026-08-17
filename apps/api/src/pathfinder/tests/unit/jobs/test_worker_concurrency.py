"""The worker runs jobs in parallel up to the configured concurrency."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import procrastinate
from procrastinate.testing import InMemoryConnector

from pathfinder.jobs.worker import amain
from pathfinder.platform.config import Settings

_OVERLAP_TIMEOUT_SECONDS = 0.25


def _default_worker_concurrency() -> int:
    """The shipped default that the worker entry point passes to procrastinate."""
    return int(Settings.model_fields["worker_concurrency"].get_default())


async def _run_two_jobs(concurrency: int) -> list[str]:
    """Defer two jobs on an in-memory app and return their ordered start/end marks.

    Each job marks its start, waits for the other job to start, then marks its
    end. A job that waits alone gives up after the timeout.
    """
    app = procrastinate.App(connector=InMemoryConnector())
    marks: list[str] = []
    both_started = asyncio.Event()

    @app.task(queue="probe", name="probe")
    async def probe(index: int) -> None:
        marks.append(f"start-{index}")
        if sum(1 for mark in marks if mark.startswith("start-")) == 2:
            both_started.set()
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(both_started.wait(), _OVERLAP_TIMEOUT_SECONDS)
        marks.append(f"end-{index}")

    async with app.open_async():
        await probe.defer_async(index=1)
        await probe.defer_async(index=2)
        await app.run_worker_async(
            queues=["probe"],
            concurrency=concurrency,
            wait=False,
            listen_notify=False,
            install_signal_handlers=False,
        )
    return marks


async def test_two_jobs_overlap_at_the_default_concurrency() -> None:
    """The second job starts while the first one still runs."""
    marks = await _run_two_jobs(_default_worker_concurrency())

    assert sorted(marks) == ["end-1", "end-2", "start-1", "start-2"]
    assert marks.index("start-2") < marks.index("end-1")


async def test_second_job_waits_at_concurrency_one() -> None:
    """The second job starts only after the first one ends."""
    marks = await _run_two_jobs(1)

    assert marks == ["start-1", "end-1", "start-2", "end-2"]


@contextlib.asynccontextmanager
async def _noop_open() -> AsyncIterator[None]:
    yield


async def _run_amain(worker_concurrency: int) -> AsyncMock:
    """Run ``amain`` against a stubbed app and return the run_worker_async mock."""
    app = MagicMock()
    app.open_async = MagicMock(side_effect=_noop_open)
    app.run_worker_async = AsyncMock()
    with (
        patch("pathfinder.jobs.worker.procrastinate_app", app),
        patch("pathfinder.jobs.worker.setup_logging"),
        patch("pathfinder.jobs.worker.install_procrastinate_redaction"),
        patch("pathfinder.jobs.worker.register_all_tools"),
        patch("pathfinder.jobs.worker._warm_up", new=AsyncMock()),
        patch(
            "pathfinder.jobs.worker.get_settings",
            return_value=MagicMock(worker_concurrency=worker_concurrency),
        ),
    ):
        await amain()
    return app.run_worker_async


async def test_amain_passes_configured_concurrency() -> None:
    """``amain`` hands the configured concurrency to the procrastinate worker."""
    run_worker_async = await _run_amain(6)

    run_worker_async.assert_awaited_once()
    assert run_worker_async.await_args.kwargs["concurrency"] == 6


async def test_amain_keeps_serving_every_queue() -> None:
    """Concurrency does not change the set of queues the worker consumes."""
    run_worker_async = await _run_amain(4)

    assert run_worker_async.await_args.kwargs["queues"] == [
        "chat_turn",
        "default",
        "maintenance",
        "verification",
    ]

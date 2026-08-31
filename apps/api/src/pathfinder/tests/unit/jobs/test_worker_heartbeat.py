"""The worker's heartbeat beats while a job holds the event loop."""

from __future__ import annotations

import asyncio
import time

import pytest

from pathfinder.jobs.heartbeat import HeartbeatThread

_BLOCK_SECONDS = 1.0
_INTERVAL_SECONDS = 0.05


def block_the_event_loop(seconds: float) -> None:
    """What a job with a synchronous call does to the worker's loop."""
    time.sleep(seconds)


async def test_the_heartbeat_beats_while_a_job_blocks_the_loop() -> None:
    """A thread of its own keeps the row advancing through a blocked loop."""
    beats: list[int] = []

    async def write(worker_id: int) -> None:
        beats.append(worker_id)

    heartbeat = HeartbeatThread(
        worker_id=lambda: 7,
        write=write,
        interval_seconds=_INTERVAL_SECONDS,
    )
    heartbeat.start()
    block_the_event_loop(_BLOCK_SECONDS)
    heartbeat.stop()

    assert len(beats) >= 10
    assert set(beats) == {7}


async def test_a_heartbeat_on_the_worker_loop_is_starved_by_the_same_job() -> None:
    """The measurement this thread exists for: a loop task beats zero times."""
    beats: list[float] = []

    async def beat_on_the_loop() -> None:
        while True:
            await asyncio.sleep(_INTERVAL_SECONDS)
            beats.append(time.monotonic())

    task = asyncio.create_task(beat_on_the_loop())
    await asyncio.sleep(0)
    block_the_event_loop(_BLOCK_SECONDS)
    task.cancel()

    assert beats == []


async def test_no_beat_before_the_worker_registers() -> None:
    """The worker id arrives after the worker starts; nothing is written first."""
    beats: list[int] = []

    async def write(worker_id: int) -> None:
        beats.append(worker_id)

    heartbeat = HeartbeatThread(
        worker_id=lambda: None,
        write=write,
        interval_seconds=_INTERVAL_SECONDS,
    )
    heartbeat.start()
    block_the_event_loop(0.3)
    heartbeat.stop()

    assert beats == []


async def test_a_wide_gap_is_reported(capfd: pytest.CaptureFixture[str]) -> None:
    """A beat that lands late names how old the last one was."""
    written = 0

    async def slow_first_write(worker_id: int) -> None:
        nonlocal written
        del worker_id
        written += 1
        if written == 2:
            await asyncio.sleep(0.6)

    heartbeat = HeartbeatThread(
        worker_id=lambda: 3,
        write=slow_first_write,
        interval_seconds=_INTERVAL_SECONDS,
    )
    heartbeat.start()
    block_the_event_loop(0.9)
    heartbeat.stop()

    assert "worker heartbeat gap" in capfd.readouterr().out


async def test_a_failed_write_does_not_stop_the_beat() -> None:
    """A database that refuses one beat does not end the heartbeat."""
    attempts = 0

    async def failing_write(worker_id: int) -> None:
        nonlocal attempts
        del worker_id
        attempts += 1
        if attempts == 1:
            msg = "connection refused"
            raise OSError(msg)

    heartbeat = HeartbeatThread(
        worker_id=lambda: 1,
        write=failing_write,
        interval_seconds=_INTERVAL_SECONDS,
    )
    heartbeat.start()
    block_the_event_loop(0.4)
    heartbeat.stop()

    assert attempts >= 3

"""Startup returns while the catalogs are still warming.

uvicorn binds its socket only after lifespan startup returns, so anything the
lifespan awaits is an outage window: the port is closed, compose dependents
mis-start, and the proxy in front answers 502.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from fastapi import FastAPI

from pathfinder import main
from pathfinder.jobs import app as jobs_app
from pathfinder.jobs import logging_filters
from pathfinder.platform import notify_dispatcher
from pathfinder.platform.langfuse import prompts
from pathfinder.platform.readiness import reset_readiness
from pathfinder.services.export import sweeper


@asynccontextmanager
async def _nothing(*_args: object, **_kwargs: object) -> AsyncIterator[None]:
    yield None


class _Registry:
    def checkpoint_types(self) -> tuple[()]:
        return ()


class _ProcrastinateApp:
    def open_async(self) -> Any:
        return _nothing()


@pytest.fixture
def isolated_lifespan(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every dependency of the lifespan except the warm-up itself."""

    async def _init_db() -> None:
        return None

    async def _sweeper_loop() -> None:
        await asyncio.Event().wait()

    monkeypatch.setattr(main, "init_db", _init_db)
    monkeypatch.setattr(main, "setup_observability", lambda **_kwargs: None)
    monkeypatch.setattr(main, "shutdown_observability", lambda: None)
    monkeypatch.setattr(main, "get_engine", lambda: None)
    monkeypatch.setattr(main, "close_db", _init_db)
    monkeypatch.setattr(main, "close_all_clients", _init_db)
    monkeypatch.setattr(main, "get_assistant_registry", _Registry)
    monkeypatch.setattr(main, "lifespan_checkpointer", _nothing)
    monkeypatch.setattr(main, "lifespan_memory_store", _nothing)
    monkeypatch.setattr(
        logging_filters, "install_procrastinate_redaction", lambda: None
    )
    monkeypatch.setattr(prompts, "seed_prompts", lambda: None)
    monkeypatch.setattr(notify_dispatcher, "lifespan_notify_dispatcher", _nothing)
    monkeypatch.setattr(jobs_app, "procrastinate_app", _ProcrastinateApp())
    monkeypatch.setattr(sweeper, "run_sweeper_loop", _sweeper_loop)


async def test_startup_returns_while_warm_up_still_runs(
    isolated_lifespan: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    del isolated_lifespan
    entered = asyncio.Event()
    release = asyncio.Event()
    finished = asyncio.Event()

    async def slow_warm_up() -> None:
        entered.set()
        await release.wait()
        finished.set()

    monkeypatch.setattr(main, "_warm_up_subsystems", slow_warm_up)

    app = FastAPI()
    async with main.lifespan(app):
        await entered.wait()
        assert not finished.is_set()
        release.set()
        await finished.wait()

    assert finished.is_set()


async def test_the_blocking_model_loads_leave_the_event_loop_free(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``warm_up_model`` holds the CPU for seconds, so it belongs on a thread."""
    callers: list[str] = []

    def record_model() -> None:
        callers.append(threading.current_thread().name)

    class _Discovery:
        async def preload_all(self) -> None:
            return None

    monkeypatch.setattr(main, "warm_up_model", record_model)
    monkeypatch.setattr(main, "warm_up_piguard", record_model)
    monkeypatch.setattr(main, "get_discovery_service", _Discovery)

    await main._warm_up_subsystems()
    reset_readiness()

    assert callers
    assert all(name != threading.main_thread().name for name in callers)

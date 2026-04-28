"""Worker boundary: run_durable_task sets ctxvar from the payload."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

import pytest

from pathfinder.jobs import runner as runner_mod
from pathfinder.jobs.runner import run_durable_task
from pathfinder.platform.context import veupathdb_auth_token_ctx


@dataclass
class _FakeContext:
    memory_store: Any = None
    user_id: UUID | None = None


class _Observer:
    observed_token: str | None = None
    call_count: int = 0


class _FakeRepo:
    def __init__(self, *, session_factory: object) -> None:
        del session_factory

    async def mark_running(self, *, task_id: UUID) -> None:
        del task_id

    async def mark_failed(self, *, task_id: UUID, error: str) -> None:
        del task_id, error

    async def mark_result_ready(self, *, task_id: UUID, result: dict[str, Any]) -> None:
        del task_id, result

    async def mark_resuming(self, *, task_id: UUID) -> None:
        del task_id

    async def mark_complete(self, *, task_id: UUID) -> None:
        del task_id


async def _observing_impl(*_: object, **__: object) -> dict[str, Any]:
    _Observer.observed_token = veupathdb_auth_token_ctx.get()
    _Observer.call_count += 1
    return {"ok": True}


async def _fake_resume_with_result(
    thread_id: str,
    task_id: UUID,
    result: dict[str, Any],
    *,
    veupathdb_auth_token: str | None = None,
) -> str | None:
    del thread_id, task_id, result, veupathdb_auth_token
    return None


async def _fake_resume_with_error(
    thread_id: str,
    task_id: UUID,
    error: str,
    *,
    veupathdb_auth_token: str | None = None,
) -> None:
    del thread_id, task_id, error, veupathdb_auth_token


class _FakeStore:
    pass


class _FakeStoreCtx:
    async def __aenter__(self) -> _FakeStore:
        return _FakeStore()

    async def __aexit__(self, *_: object) -> None:
        return None


def _fake_lifespan_memory_store(*_: object, **__: object) -> _FakeStoreCtx:
    return _FakeStoreCtx()


async def _fake_build_worker_runtime_context(**kwargs: Any) -> _FakeContext:
    del kwargs
    return _FakeContext()


@pytest.fixture(autouse=True)
def _reset_observer() -> None:
    _Observer.observed_token = "sentinel-unreset"
    _Observer.call_count = 0


@pytest.mark.asyncio
async def test_run_durable_task_sets_ctxvar_from_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        runner_mod.TOOL_REGISTRY, "stub_tool", _observing_impl,
    )
    monkeypatch.setattr(runner_mod, "BackgroundTaskRepository", _FakeRepo)
    monkeypatch.setattr(
        runner_mod, "lifespan_memory_store", _fake_lifespan_memory_store,
    )
    monkeypatch.setattr(
        runner_mod,
        "build_worker_runtime_context",
        _fake_build_worker_runtime_context,
    )
    monkeypatch.setattr(
        runner_mod,
        "_safe_resume_graph_with_result",
        _fake_resume_with_result,
    )
    monkeypatch.setattr(
        runner_mod,
        "_safe_resume_graph_with_error",
        _fake_resume_with_error,
    )

    await run_durable_task(
        tool_name="stub_tool",
        task_id=str(uuid4()),
        thread_id=str(uuid4()),
        args={"kwargs": {}},
        veupathdb_auth_token="worker-token-abc",
    )

    assert _Observer.call_count == 1
    assert _Observer.observed_token == "worker-token-abc"


@pytest.mark.asyncio
async def test_run_durable_task_resets_ctxvar_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        runner_mod.TOOL_REGISTRY, "stub_tool", _observing_impl,
    )
    monkeypatch.setattr(runner_mod, "BackgroundTaskRepository", _FakeRepo)
    monkeypatch.setattr(
        runner_mod, "lifespan_memory_store", _fake_lifespan_memory_store,
    )
    monkeypatch.setattr(
        runner_mod,
        "build_worker_runtime_context",
        _fake_build_worker_runtime_context,
    )
    monkeypatch.setattr(
        runner_mod,
        "_safe_resume_graph_with_result",
        _fake_resume_with_result,
    )
    monkeypatch.setattr(
        runner_mod,
        "_safe_resume_graph_with_error",
        _fake_resume_with_error,
    )

    assert veupathdb_auth_token_ctx.get() is None

    await run_durable_task(
        tool_name="stub_tool",
        task_id=str(uuid4()),
        thread_id=str(uuid4()),
        args={"kwargs": {}},
        veupathdb_auth_token="tok",
    )

    assert veupathdb_auth_token_ctx.get() is None


@pytest.mark.asyncio
async def test_run_durable_task_none_token_is_ok(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        runner_mod.TOOL_REGISTRY, "stub_tool", _observing_impl,
    )
    monkeypatch.setattr(runner_mod, "BackgroundTaskRepository", _FakeRepo)
    monkeypatch.setattr(
        runner_mod, "lifespan_memory_store", _fake_lifespan_memory_store,
    )
    monkeypatch.setattr(
        runner_mod,
        "build_worker_runtime_context",
        _fake_build_worker_runtime_context,
    )
    monkeypatch.setattr(
        runner_mod,
        "_safe_resume_graph_with_result",
        _fake_resume_with_result,
    )
    monkeypatch.setattr(
        runner_mod,
        "_safe_resume_graph_with_error",
        _fake_resume_with_error,
    )

    await run_durable_task(
        tool_name="stub_tool",
        task_id=str(uuid4()),
        thread_id=str(uuid4()),
        args={"kwargs": {}},
        veupathdb_auth_token=None,
    )

    assert _Observer.observed_token is None

from __future__ import annotations

import json
from typing import Any, ClassVar
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools import durable as durable_mod
from pathfinder.ai.tools.durable import durable_tool
from pathfinder.domain.strategy.session import StrategySession


class _FakeInterruptError(Exception):
    def __init__(self, payload: dict[str, Any]) -> None:
        super().__init__("fake interrupt")
        self.payload = payload


class _FakeRepo:
    created: ClassVar[list[dict[str, Any]]] = []


async def _fake_create_background_task(
    *,
    conversation_id: UUID,
    user_id: UUID,
    tool_name: str,
    args: dict[str, Any],
    estimated_duration_seconds: int,
) -> UUID:
    _FakeRepo.created.append(
        {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "tool_name": tool_name,
            "args": args,
            "estimated_duration_seconds": estimated_duration_seconds,
        }
    )
    return UUID("00000000-0000-0000-0000-000000000001")


class _FakeTask:
    deferred: ClassVar[list[dict[str, Any]]] = []

    async def defer_async(self, **kwargs: Any) -> int:
        _FakeTask.deferred.append(kwargs)
        return 42


class _FakeApp:
    def __init__(self) -> None:
        self._configured: list[tuple[str, str]] = []

    def configure_task(self, *, name: str, queue: str) -> _FakeTask:
        self._configured.append((name, queue))
        return _FakeTask()

    def open_async(self) -> _FakeAppCtx:
        return _FakeAppCtx()


class _FakeAppCtx:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *args: object) -> None:
        return None


class _RunCtx:
    def __init__(self, deps: AgentDeps) -> None:
        self.deps = deps


def _raise_interrupt(payload: dict[str, Any]) -> Any:
    raise _FakeInterruptError(payload)


def _fresh_deps(conversation_id: UUID | None, user_id: UUID | None) -> AgentDeps:
    return AgentDeps(
        site_id="plasmodb",
        user_id=user_id,
        strategy_session=StrategySession(site_id="plasmodb"),
        conversation_id=conversation_id,
    )


@pytest.mark.asyncio
async def test_durable_tool_submits_job_and_interrupts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeRepo.created.clear()
    _FakeTask.deferred.clear()
    monkeypatch.setattr(durable_mod, "interrupt", _raise_interrupt)
    monkeypatch.setattr(
        durable_mod, "create_background_task", _fake_create_background_task
    )
    monkeypatch.setattr(durable_mod, "procrastinate_app", _FakeApp())

    @durable_tool(tool_name="stub_tool", estimated_duration_seconds=60)
    async def stub_tool(ctx: _RunCtx, x: int) -> dict[str, Any]:
        del ctx, x
        msg = "agent-side body must not execute"
        raise AssertionError(msg)

    conversation_id = uuid4()
    user_id = uuid4()
    ctx = _RunCtx(deps=_fresh_deps(conversation_id, user_id))

    with pytest.raises(_FakeInterruptError) as excinfo:
        await stub_tool(ctx, x=5)

    payload = excinfo.value.payload
    assert payload["kind"] == "durable_task"
    assert payload["tool_name"] == "stub_tool"
    assert payload["estimated_duration_seconds"] == 60
    assert payload["task_id"] == "00000000-0000-0000-0000-000000000001"

    assert len(_FakeRepo.created) == 1
    created = _FakeRepo.created[0]
    assert created["tool_name"] == "stub_tool"
    assert created["conversation_id"] == conversation_id
    assert created["user_id"] == user_id
    assert created["estimated_duration_seconds"] == 60
    assert created["args"] == {"args": [], "kwargs": {"x": 5}}

    assert len(_FakeTask.deferred) == 1
    deferred = _FakeTask.deferred[0]
    assert deferred["task_id"] == "00000000-0000-0000-0000-000000000001"
    assert deferred["thread_id"] == str(conversation_id)
    assert deferred["args"] == {"args": [], "kwargs": {"x": 5}}


class _SampleTarget(BaseModel):
    name: str
    thresholds: list[float]


@pytest.mark.asyncio
async def test_durable_tool_serializes_pydantic_kwargs_to_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression for Bug 2: BaseModel kwargs must round-trip via JSON.

    Procrastinate persists job args via ``json.dumps``. Raw BaseModel
    instances crash. The decorator must ``model_dump`` them before defer.
    """
    _FakeRepo.created.clear()
    _FakeTask.deferred.clear()
    monkeypatch.setattr(durable_mod, "interrupt", _raise_interrupt)
    monkeypatch.setattr(
        durable_mod, "create_background_task", _fake_create_background_task
    )
    monkeypatch.setattr(durable_mod, "procrastinate_app", _FakeApp())

    @durable_tool(tool_name="stub", estimated_duration_seconds=10)
    async def stub(ctx: _RunCtx, target: _SampleTarget) -> dict[str, Any]:
        del ctx, target
        msg = "must not execute"
        raise AssertionError(msg)

    ctx = _RunCtx(deps=_fresh_deps(conversation_id=uuid4(), user_id=uuid4()))
    target = _SampleTarget(name="x", thresholds=[0.1, 0.05])

    with pytest.raises(_FakeInterruptError):
        await stub(ctx, target=target)

    assert len(_FakeTask.deferred) == 1
    deferred_args = _FakeTask.deferred[0]["args"]
    # must be JSON-serialisable — this is what Procrastinate actually does
    serialized = json.dumps(deferred_args)
    round_tripped = json.loads(serialized)
    assert round_tripped["kwargs"]["target"] == {
        "name": "x",
        "thresholds": [0.1, 0.05],
    }

    # created row must have the same JSON-safe shape
    created_args = _FakeRepo.created[0]["args"]
    json.dumps(created_args)  # must not raise


@pytest.mark.asyncio
async def test_durable_tool_raises_when_conversation_id_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeRepo.created.clear()
    _FakeTask.deferred.clear()
    monkeypatch.setattr(durable_mod, "interrupt", _raise_interrupt)
    monkeypatch.setattr(
        durable_mod, "create_background_task", _fake_create_background_task
    )
    monkeypatch.setattr(durable_mod, "procrastinate_app", _FakeApp())

    @durable_tool(tool_name="stub_tool", estimated_duration_seconds=60)
    async def stub_tool(ctx: _RunCtx) -> dict[str, Any]:
        del ctx
        msg = "agent-side body must not execute"
        raise AssertionError(msg)

    ctx = _RunCtx(deps=_fresh_deps(conversation_id=None, user_id=uuid4()))
    with pytest.raises(RuntimeError, match="conversation_id"):
        await stub_tool(ctx)

    assert _FakeRepo.created == []
    assert _FakeTask.deferred == []


@pytest.mark.asyncio
async def test_durable_tool_raises_when_user_id_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeRepo.created.clear()
    _FakeTask.deferred.clear()
    monkeypatch.setattr(durable_mod, "interrupt", _raise_interrupt)
    monkeypatch.setattr(
        durable_mod, "create_background_task", _fake_create_background_task
    )
    monkeypatch.setattr(durable_mod, "procrastinate_app", _FakeApp())

    @durable_tool(tool_name="stub_tool", estimated_duration_seconds=60)
    async def stub_tool(ctx: _RunCtx) -> dict[str, Any]:
        del ctx
        msg = "agent-side body must not execute"
        raise AssertionError(msg)

    ctx = _RunCtx(deps=_fresh_deps(conversation_id=uuid4(), user_id=None))
    with pytest.raises(RuntimeError, match="user_id"):
        await stub_tool(ctx)

    assert _FakeRepo.created == []
    assert _FakeTask.deferred == []

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

import pathfinder.services.parameter_optimization.core
from pathfinder.ai.tools.durable import TaskProgressEmitter
from pathfinder.jobs.impls import optimize_params_impl, register_all_tools
from pathfinder.jobs.impls.optimize_params_impl import (
    optimize_search_parameters_impl,
)
from pathfinder.jobs.registry import TOOL_REGISTRY
from pathfinder.jobs.runner import run_durable_task
from pathfinder.persistence.models import (
    BackgroundTask,
    Chat,
    TaskProgress,
    User,
)
from pathfinder.persistence.repositories.background_tasks import (
    BackgroundTaskRepository,
)
from pathfinder.persistence.session import async_session_factory


class _FakeOptimizationResult:
    def model_dump(self, **_kwargs: Any) -> dict[str, Any]:
        return {
            "bestConfig": {"foo": "1"},
            "trials": [
                {"trialIndex": 0, "score": 0.8},
                {"trialIndex": 1, "score": 0.9},
            ],
            "paretoFrontier": [],
            "sensitivity": {},
        }


async def _fake_core_optimize(
    inp: Any,
    config: Any = None,
    progress_callback: Any = None,
    check_cancelled: Any = None,
) -> _FakeOptimizationResult:
    del inp, config, check_cancelled
    if progress_callback is not None:
        await progress_callback(
            {
                "event": "trial_complete",
                "data": {"trialIndex": 0, "score": 0.8},
            }
        )
        await progress_callback(
            {
                "event": "trial_complete",
                "data": {"trialIndex": 1, "score": 0.9},
            }
        )
    return _FakeOptimizationResult()


async def _fake_attach_export(
    result_json: dict[str, Any], search_name: str
) -> None:
    del search_name
    result_json["downloads"] = {"jsonUrl": "https://ex/opt.json"}


async def _seed_user_chat(user_id: UUID, chat_id: UUID) -> None:
    async with async_session_factory() as session:
        session.add(User(id=user_id))
        await session.flush()
        session.add(
            Chat(id=chat_id, user_id=user_id, site_id="plasmodb", name="")
        )
        await session.commit()


class _FakeContext:
    def __init__(self, site_id: str) -> None:
        self.site_id = site_id


@pytest.fixture
def target_kwargs() -> dict[str, Any]:
    return {
        "target": {
            "site_id": "plasmodb",
            "record_type": "transcript",
            "search_name": "GenesByExpression",
            "fixed_parameters": {},
            "parameter_space": [
                {
                    "name": "threshold",
                    "type": "numeric",
                    "min_value": 0.0,
                    "max_value": 1.0,
                    "log_scale": False,
                    "choices": None,
                }
            ],
        },
        "controls": {
            "positive_controls": ["a", "b"],
            "negative_controls": [],
            "controls_search_name": "GeneByLocusTag",
            "controls_param_name": "ds_gene_ids",
            "controls_value_format": "newline",
            "controls_extra_parameters": {},
            "id_field": "primary_key",
        },
        "settings": {
            "budget": 2,
            "objective": "f1",
            "beta": 1.0,
            "method": "bayesian",
            "estimated_size_penalty": 0.0,
        },
    }


def test_optimize_search_parameters_registered_in_registry() -> None:
    register_all_tools()
    assert "optimize_search_parameters" in TOOL_REGISTRY
    assert (
        TOOL_REGISTRY["optimize_search_parameters"]
        is optimize_search_parameters_impl
    )


@pytest.mark.asyncio
async def test_optimize_impl_emits_per_trial_progress(
    db_cleaner: None,
    patch_app_db_engine: None,
    monkeypatch: pytest.MonkeyPatch,
    target_kwargs: dict[str, Any],
) -> None:
    del db_cleaner, patch_app_db_engine

    monkeypatch.setattr(
        pathfinder.services.parameter_optimization.core,
        "optimize_search_parameters",
        _fake_core_optimize,
    )
    monkeypatch.setattr(
        optimize_params_impl, "_attach_export", _fake_attach_export
    )

    user_id = uuid4()
    chat_id = uuid4()
    task_id = uuid4()
    await _seed_user_chat(user_id, chat_id)

    async with async_session_factory() as session:
        session.add(
            BackgroundTask(
                id=task_id,
                chat_id=chat_id,
                user_id=user_id,
                tool_name="optimize_search_parameters",
                status="running",
                args={},
                estimated_duration_seconds=300,
            )
        )
        await session.commit()

    progress = TaskProgressEmitter(
        task_id=task_id,
        chat_id=chat_id,
        session_factory=async_session_factory,
    )

    result = await optimize_search_parameters_impl(
        context=_FakeContext(site_id="plasmodb"),
        task_id=task_id,
        progress=progress,
        memory_store=None,
        **target_kwargs,
    )

    assert isinstance(result, dict)
    assert result["bestConfig"] == {"foo": "1"}
    assert result["downloads"]["jsonUrl"] == "https://ex/opt.json"

    async with async_session_factory() as session:
        rows = list(
            (
                await session.execute(
                    select(TaskProgress)
                    .where(TaskProgress.task_id == task_id)
                    .order_by(TaskProgress.id)
                )
            ).scalars()
        )

    trial_rows = [r for r in rows if (r.data or {}).get("trialIndex") is not None]
    assert len(trial_rows) == 2
    assert trial_rows[0].data == {"trialIndex": 0, "score": 0.8}
    assert trial_rows[1].data == {"trialIndex": 1, "score": 0.9}


@pytest.mark.asyncio
async def test_run_durable_task_wiring_optimize(
    db_cleaner: None,
    patch_app_db_engine: None,
    monkeypatch: pytest.MonkeyPatch,
    target_kwargs: dict[str, Any],
) -> None:
    del db_cleaner, patch_app_db_engine

    monkeypatch.setattr(
        pathfinder.services.parameter_optimization.core,
        "optimize_search_parameters",
        _fake_core_optimize,
    )
    monkeypatch.setattr(
        optimize_params_impl, "_attach_export", _fake_attach_export
    )
    register_all_tools()

    user_id = uuid4()
    chat_id = uuid4()
    await _seed_user_chat(user_id, chat_id)

    repo = BackgroundTaskRepository(session_factory=async_session_factory)
    task_id = await repo.create(
        chat_id=chat_id,
        user_id=user_id,
        tool_name="optimize_search_parameters",
        args={"args": [], "kwargs": target_kwargs},
        estimated_duration_seconds=900,
    )

    await run_durable_task(
        tool_name="optimize_search_parameters",
        task_id=str(task_id),
        thread_id=str(chat_id),
        args={"args": [], "kwargs": target_kwargs},
    )

    t = await repo.get(task_id=task_id)
    assert t is not None
    assert t.status in ("complete", "resuming", "result_ready")
    assert t.result is not None
    assert t.result["bestConfig"] == {"foo": "1"}

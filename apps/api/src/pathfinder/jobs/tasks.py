"""Procrastinate task registrations for the Pathfinder worker.

All tasks register on import via the ``@procrastinate_app.task`` decorator.
``ensure_registered`` is a no-op call-site marker used by the bootstrap
path so importing this module is not flagged as an unused import.
"""

from __future__ import annotations

from typing import Any

from pathfinder.jobs.app import procrastinate_app
from pathfinder.jobs.impls.chat_turn_impl import run_chat_turn
from pathfinder.jobs.runner import run_durable_task


def ensure_registered() -> None:
    """No-op that keeps the module-import side effects live.

    The real work is the ``@procrastinate_app.task`` decorators below — those
    run at import time. This function exists so callers that need to
    guarantee tasks are registered (the worker bootstrap path) can reference
    the module without relying on unused-import semantics.
    """


@procrastinate_app.task(queue="default", name="echo")
async def echo_task(message: str) -> str:
    """Smoke task for worker/app bring-up tests."""
    return message


@procrastinate_app.task(
    queue="verification", name="durable:run_control_tests_on_step"
)
async def run_control_tests_on_step_job(
    task_id: str,
    thread_id: str,
    args: dict[str, Any],
    veupathdb_auth_token: str | None = None,
) -> None:
    await run_durable_task(
        tool_name="run_control_tests_on_step",
        task_id=task_id,
        thread_id=thread_id,
        args=args,
        veupathdb_auth_token=veupathdb_auth_token,
    )


@procrastinate_app.task(
    queue="verification", name="durable:optimize_search_parameters"
)
async def optimize_search_parameters_job(
    task_id: str,
    thread_id: str,
    args: dict[str, Any],
    veupathdb_auth_token: str | None = None,
) -> None:
    await run_durable_task(
        tool_name="optimize_search_parameters",
        task_id=task_id,
        thread_id=thread_id,
        args=args,
        veupathdb_auth_token=veupathdb_auth_token,
    )


@procrastinate_app.task(
    queue="verification", name="durable:geneset_enrichment"
)
async def geneset_enrichment_job(
    task_id: str,
    thread_id: str,
    args: dict[str, Any],
    veupathdb_auth_token: str | None = None,
) -> None:
    await run_durable_task(
        tool_name="geneset_enrichment",
        task_id=task_id,
        thread_id=thread_id,
        args=args,
        veupathdb_auth_token=veupathdb_auth_token,
    )


@procrastinate_app.task(queue="chat_turn", name="chat_turn:run")
async def run_chat_turn_job(payload: dict[str, Any]) -> None:
    await run_chat_turn(payload)

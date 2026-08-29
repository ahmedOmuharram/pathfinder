from __future__ import annotations

import pytest

from pathfinder.jobs.app import procrastinate_app
from pathfinder.jobs.tasks import (
    geneset_enrichment_job,
    optimize_search_parameters_job,
    run_control_tests_on_step_job,
    run_eda_compute_job,
)


def test_durable_tasks_registered_on_verification_queue() -> None:
    tasks = procrastinate_app.tasks
    assert "durable:run_control_tests_on_step" in tasks
    assert "durable:optimize_search_parameters" in tasks
    assert "durable:geneset_enrichment" in tasks
    assert "durable:run_eda_compute" in tasks
    assert tasks["durable:run_eda_compute"].queue == "verification"

    assert tasks["durable:run_control_tests_on_step"].queue == "verification", tasks[
        "durable:run_control_tests_on_step"
    ].queue
    assert tasks["durable:optimize_search_parameters"].queue == "verification", tasks[
        "durable:optimize_search_parameters"
    ].queue
    assert tasks["durable:geneset_enrichment"].queue == "verification", tasks[
        "durable:geneset_enrichment"
    ].queue


@pytest.mark.asyncio
async def test_durable_tasks_can_be_deferred(
    db_cleaner: None, patch_app_db_engine: None
) -> None:
    del db_cleaner, patch_app_db_engine
    async with procrastinate_app.open_async():
        job_ids = [
            await run_control_tests_on_step_job.defer_async(
                task_id="00000000-0000-0000-0000-000000000001",
                thread_id="00000000-0000-0000-0000-000000000002",
                args={"args": [], "kwargs": {}},
            ),
            await optimize_search_parameters_job.defer_async(
                task_id="00000000-0000-0000-0000-000000000003",
                thread_id="00000000-0000-0000-0000-000000000004",
                args={"args": [], "kwargs": {}},
            ),
            await geneset_enrichment_job.defer_async(
                task_id="00000000-0000-0000-0000-000000000005",
                thread_id="00000000-0000-0000-0000-000000000006",
                args={"args": [], "kwargs": {}},
            ),
            await run_eda_compute_job.defer_async(
                task_id="00000000-0000-0000-0000-000000000007",
                thread_id="00000000-0000-0000-0000-000000000008",
                args={"args": [], "kwargs": {}},
            ),
        ]
    for jid in job_ids:
        assert isinstance(jid, int)
        assert jid > 0

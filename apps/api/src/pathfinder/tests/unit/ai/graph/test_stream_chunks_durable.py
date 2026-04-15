from __future__ import annotations

import json

from pathfinder.ai.graph.stream_chunks import (
    background_task_started_chunk,
    encode_chunk_as_sse,
)


def test_background_task_started_chunk_shape() -> None:
    chunk = background_task_started_chunk(
        task_id="abc",
        tool_name="run_control_tests_on_step",
        estimated_duration_seconds=180,
    )
    assert chunk.type == "data-background-task-started"
    assert chunk.data == {
        "taskId": "abc",
        "toolName": "run_control_tests_on_step",
        "estimatedDurationSeconds": 180,
    }


def test_background_task_started_chunk_sse_encoding() -> None:
    chunk = background_task_started_chunk(
        task_id="task-1",
        tool_name="optimize_search_parameters",
        estimated_duration_seconds=900,
    )
    sse = encode_chunk_as_sse(chunk)
    assert sse.startswith("data: ")
    assert sse.endswith("\n\n")

    payload = json.loads(sse.removeprefix("data: ").strip())
    assert payload["type"] == "data-background-task-started"
    assert payload["data"]["taskId"] == "task-1"
    assert payload["data"]["toolName"] == "optimize_search_parameters"
    assert payload["data"]["estimatedDurationSeconds"] == 900

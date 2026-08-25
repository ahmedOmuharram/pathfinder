"""The per-task channel is deprecated, so its bytes are pinned.

PROTOCOL.md section 13 specifies the dialect this endpoint speaks. A client
built against that section reads these exact frames, and a change to them is a
change to a channel that promises not to change.
"""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from assistant_core.persistence.models import Conversation
from assistant_core.platform.db import async_session_factory

from pathfinder.jobs.progress import TaskProgressEmitter
from pathfinder.persistence.models import BackgroundTask
from pathfinder.persistence.repositories.background_tasks import (
    BackgroundTaskRepository,
)
from pathfinder.tests.protocol_document import protocol_section

# The closing newline is a frame terminator, so it is part of the capture.
_FENCE = re.compile(r"```text\n(.*?)```", re.DOTALL)
_ZERO_UUID = "00000000-0000-0000-0000-000000000000"


def _documented_frames() -> str:
    fence = _FENCE.search(protocol_section("legacy_frames"))
    assert fence is not None, "the legacy_frames section fences no block"
    return fence.group(1)


async def _seed(*, user_id: UUID, conversation_id: UUID, task_id: UUID) -> None:
    async with async_session_factory() as session:
        session.add(
            Conversation(
                id=conversation_id,
                user_id=user_id,
                site_id="plasmodb",
                name="",
            ),
        )
        await session.flush()
        session.add(
            BackgroundTask(
                id=task_id,
                conversation_id=conversation_id,
                user_id=user_id,
                tool_name="run_control_tests_on_step",
                status="running",
                args={},
                estimated_duration_seconds=30,
            ),
        )
        await session.commit()


@pytest.mark.asyncio
async def test_the_per_task_channel_frames_what_the_document_says(
    authed_client: httpx.AsyncClient,
    authed_user_id: UUID,
    app_notify_dispatcher: Any,
) -> None:
    del app_notify_dispatcher
    conversation_id, task_id = uuid4(), uuid4()
    await _seed(
        user_id=authed_user_id,
        conversation_id=conversation_id,
        task_id=task_id,
    )
    emitter = TaskProgressEmitter(
        task_id=task_id,
        conversation_id=conversation_id,
        session_factory=async_session_factory,
    )
    await emitter.update(percent=0.25, message="loading data", data={"step": "a"})
    repo = BackgroundTaskRepository(session_factory=async_session_factory)
    await repo.mark_result_ready(task_id=task_id, result={"ok": True})
    await repo.mark_complete(task_id=task_id)

    response = await authed_client.get(
        f"/api/v1/conversations/{conversation_id}/tasks/{task_id}/events",
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.text.replace(str(task_id), _ZERO_UUID) == _documented_frames()

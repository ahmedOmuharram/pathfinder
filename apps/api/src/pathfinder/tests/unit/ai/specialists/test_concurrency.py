from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from pathfinder.ai.specialists.concurrency import (
    ActiveSessionConflictError,
    ActiveSessionReason,
    assert_no_active_session,
)


async def test_no_active_session_raises_when_specialist_mode_set() -> None:
    conv = MagicMock()
    conv.specialist_mode = {"kind": "validate"}
    conv.id = uuid4()
    with pytest.raises(ActiveSessionConflictError) as ei:
        await assert_no_active_session(conversation=conv)
    assert ei.value.reason == ActiveSessionReason.SPECIALIST_ACTIVE


async def test_no_active_session_raises_when_durable_task_active() -> None:
    conv = MagicMock()
    conv.specialist_mode = None
    conv.id = uuid4()
    fake_task = MagicMock()
    fake_task.tool_name = "run_control_tests_on_step"
    fake_task.completed_at = datetime.now(UTC)

    bg_repo_instance = MagicMock()
    bg_repo_instance.list_active_for_conversation = AsyncMock(
        return_value=[fake_task],
    )

    with patch(
        "pathfinder.ai.specialists.concurrency.BackgroundTaskRepository",
        return_value=bg_repo_instance,
    ), pytest.raises(ActiveSessionConflictError) as ei:
        await assert_no_active_session(conversation=conv)
    assert ei.value.reason == ActiveSessionReason.DURABLE_TASK_ACTIVE
    assert "run_control_tests_on_step" in ei.value.detail


async def test_no_active_session_passes_when_clean() -> None:
    conv = MagicMock()
    conv.specialist_mode = None
    conv.id = uuid4()
    bg_repo_instance = MagicMock()
    bg_repo_instance.list_active_for_conversation = AsyncMock(return_value=[])
    with patch(
        "pathfinder.ai.specialists.concurrency.BackgroundTaskRepository",
        return_value=bg_repo_instance,
    ):
        await assert_no_active_session(conversation=conv)

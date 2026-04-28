from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from pathfinder.ai.memory.schemas import MemoryEntryDraft
from pathfinder.ai.specialists import concurrency as concurrency_mod
from pathfinder.ai.tools.standalone.exit_specialist import (
    ExitSpecialistResult,
    exit_specialist,
)


@asynccontextmanager
async def _async_session_cm(session: Any) -> AsyncIterator[Any]:
    yield session


def _ctx(
    *, conversation_id: UUID | None, user_id: UUID | None,
    with_findings_support: bool = True,
) -> tuple[Any, Any, Any]:
    deps = MagicMock()
    deps.user_id = user_id
    deps.site_id = "plasmodb"
    deps.conversation_id = conversation_id
    deps.memory_store = MagicMock() if with_findings_support else None

    fake_session = MagicMock()
    fake_session.commit = AsyncMock()
    deps.db_session_factory = lambda: _async_session_cm(fake_session)

    ctx = MagicMock()
    ctx.deps = deps
    return ctx, deps, fake_session


async def test_exit_specialist_clears_mode_when_no_findings(monkeypatch):
    conversation_id = uuid4()
    user_id = uuid4()
    ctx, _deps, _fake_session = _ctx(
        conversation_id=conversation_id, user_id=user_id,
    )

    fake_repo = MagicMock()
    fake_repo.update_conversation = AsyncMock()
    monkeypatch.setattr(
        "pathfinder.ai.tools.standalone.exit_specialist.ConversationRepository",
        lambda _session: fake_repo,
    )

    result = await exit_specialist(ctx, summary="all good", findings=None)
    payload = result.return_value
    assert isinstance(payload, ExitSpecialistResult)
    assert payload.cleared is True
    assert payload.autowritten_count == 0

    fake_repo.update_conversation.assert_awaited_once()
    args, _ = fake_repo.update_conversation.call_args
    assert args[0] == conversation_id


async def test_exit_specialist_writes_findings_through_autowrite(monkeypatch):
    conversation_id = uuid4()
    user_id = uuid4()
    ctx, _deps, _fake_session = _ctx(
        conversation_id=conversation_id, user_id=user_id,
    )

    fake_repo = MagicMock()
    fake_repo.update_conversation = AsyncMock()
    monkeypatch.setattr(
        "pathfinder.ai.tools.standalone.exit_specialist.ConversationRepository",
        lambda _session: fake_repo,
    )

    write_calls: list[tuple[list[MemoryEntryDraft], Any]] = []

    async def fake_write(
        *, store: Any, tombstones: Any, drafts: list[MemoryEntryDraft],
        context: Any,
    ) -> int:
        _ = store, tombstones
        write_calls.append((drafts, context))
        return len(drafts)

    monkeypatch.setattr(
        "pathfinder.ai.tools.standalone.exit_specialist.write_drafts_with_tombstones",
        fake_write,
    )
    monkeypatch.setattr(
        "pathfinder.ai.tools.standalone.exit_specialist.MemoryStore",
        lambda store: store,
    )
    monkeypatch.setattr(
        "pathfinder.ai.tools.standalone.exit_specialist.TombstoneRepository",
        lambda session_factory: session_factory,
    )

    findings = [
        MemoryEntryDraft(
            name="organism kinome",
            summary="Pf has 86 kinases",
            content={"organism": "Pf", "kinome_size": 86},
        ),
    ]
    result = await exit_specialist(
        ctx, summary="validated", findings=findings,
    )
    payload = result.return_value
    assert isinstance(payload, ExitSpecialistResult)
    assert payload.cleared is True
    assert payload.autowritten_count == 1
    assert len(write_calls) == 1
    drafts, context = write_calls[0]
    assert drafts == findings
    assert context.user_id == user_id
    assert context.kind == "knowledge"
    assert context.source_conversation_id == conversation_id


async def test_exit_specialist_skips_autowrite_when_no_user_id(monkeypatch):
    conversation_id = uuid4()
    ctx, _deps, _fake_session = _ctx(
        conversation_id=conversation_id, user_id=None,
    )

    fake_repo = MagicMock()
    fake_repo.update_conversation = AsyncMock()
    monkeypatch.setattr(
        "pathfinder.ai.tools.standalone.exit_specialist.ConversationRepository",
        lambda _session: fake_repo,
    )

    result = await exit_specialist(
        ctx,
        summary="ok",
        findings=[
            MemoryEntryDraft(name="x", summary="y", content={}),
        ],
    )
    payload = result.return_value
    assert isinstance(payload, ExitSpecialistResult)
    assert payload.autowritten_count == 0
    assert payload.cleared is True


async def test_assert_no_inflight_durable_task_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bg_repo_instance = MagicMock()
    fake_task = MagicMock()
    fake_task.tool_name = "run_control_tests_on_step"
    bg_repo_instance.list_active_for_conversation = AsyncMock(
        return_value=[fake_task],
    )
    def _fake_repo_factory(*, session_factory: Any) -> Any:
        del session_factory
        return bg_repo_instance

    monkeypatch.setattr(
        concurrency_mod, "BackgroundTaskRepository", _fake_repo_factory,
    )
    with pytest.raises(concurrency_mod.ActiveSessionConflictError):
        await concurrency_mod.assert_no_inflight_durable_task(
            conversation_id=uuid4(),
        )

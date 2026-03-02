from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from veupath_chatbot.services.chat.processor import ChatStreamProcessor
from veupath_chatbot.tests.fixtures.event_builders import (
    assistant_message_event,
    citations_event,
    graph_cleared_event,
    graph_plan_event,
    graph_snapshot_event,
    optimization_progress_event,
    planning_artifact_event,
    reasoning_event,
    strategy_meta_event,
    subkani_task_end_event,
    subkani_task_start_event,
    subkani_tool_call_end_event,
    subkani_tool_call_start_event,
    tool_call_end_event,
    tool_call_start_event,
)
from veupath_chatbot.tests.fixtures.fake_repos import FakeStrategyRepo


def _make_processor(
    *, repo: FakeStrategyRepo | None = None, strategy_id=None, mode: str = "execute"
):
    repo = repo or FakeStrategyRepo()
    sid = strategy_id or uuid4()
    strategy = SimpleNamespace(id=sid, wdk_strategy_id=None)
    processor = ChatStreamProcessor(
        strategy_repo=repo,
        site_id="plasmodb",
        user_id=uuid4(),
        strategy=strategy,
        strategy_payload={"id": str(sid)},
        mode=mode,
    )
    return processor, repo


# ── Existing test (updated to use shared fixtures) ──


@pytest.mark.asyncio
async def test_strategy_link_updates_active_strategy_and_commits_mid_stream() -> None:
    repo = FakeStrategyRepo()
    current_strategy_id = uuid4()
    strategy = SimpleNamespace(id=current_strategy_id, wdk_strategy_id=None)
    processor = ChatStreamProcessor(
        strategy_repo=repo,
        site_id="plasmodb",
        user_id=uuid4(),
        strategy=strategy,
        strategy_payload={"id": str(current_strategy_id)},
        mode="execute",
    )

    other_graph_id = str(uuid4())
    line = await processor.on_event(
        "strategy_link",
        {"graphId": other_graph_id, "wdkStrategyId": 12345, "name": "Built strategy"},
    )

    assert line is not None
    assert len(repo.updated) == 1
    assert repo.updated[0]["strategy_id"] == current_strategy_id
    assert repo.updated[0]["wdk_strategy_id"] == 12345
    assert repo.updated[0]["wdk_strategy_id_set"] is True
    assert repo.created == []
    assert repo.session.commit_calls == 1
    assert processor.pending_strategy_link[str(current_strategy_id)]["graphId"] == str(
        current_strategy_id
    )


# ── New tests ──


@pytest.mark.asyncio
async def test_message_start_returns_none() -> None:
    """message_start is skipped by on_event (start_event is separate)."""
    proc, _ = _make_processor()
    result = await proc.on_event("message_start", {})
    assert result is None


@pytest.mark.asyncio
async def test_assistant_message_accumulates_content() -> None:
    proc, _ = _make_processor()
    await proc.on_event("assistant_message", assistant_message_event("Hello"))
    await proc.on_event("assistant_message", assistant_message_event("World"))
    assert proc.assistant_messages == ["Hello", "World"]


@pytest.mark.asyncio
async def test_assistant_message_sanitizes_content() -> None:
    proc, _ = _make_processor()
    await proc.on_event("assistant_message", {"content": "hello"})
    assert proc.assistant_messages == ["hello"]


@pytest.mark.asyncio
async def test_tool_call_events_tracked() -> None:
    proc, _ = _make_processor()
    await proc.on_event(
        "tool_call_start", tool_call_start_event("t1", "search", '{"q":"abc"}')
    )
    assert "t1" in proc.tool_calls_by_id
    assert proc.tool_calls_by_id["t1"]["name"] == "search"

    await proc.on_event("tool_call_end", tool_call_end_event("t1", '{"results":[]}'))
    assert len(proc.tool_calls) == 1
    assert proc.tool_calls[0]["result"] == '{"results":[]}'


@pytest.mark.asyncio
async def test_tool_call_end_unknown_id_ignored() -> None:
    proc, _ = _make_processor()
    await proc.on_event("tool_call_end", tool_call_end_event("unknown"))
    assert len(proc.tool_calls) == 0


@pytest.mark.asyncio
async def test_citations_collected() -> None:
    proc, _ = _make_processor()
    await proc.on_event("citations", citations_event([{"id": "c1", "title": "T"}]))
    assert len(proc.citations) == 1
    assert proc.citations[0]["id"] == "c1"


@pytest.mark.asyncio
async def test_planning_artifact_collected() -> None:
    proc, _ = _make_processor()
    await proc.on_event("planning_artifact", planning_artifact_event("a1", "Plan"))
    assert len(proc.planning_artifacts) == 1
    assert proc.planning_artifacts[0]["id"] == "a1"


@pytest.mark.asyncio
async def test_reasoning_captured() -> None:
    proc, _ = _make_processor()
    await proc.on_event("reasoning", reasoning_event("Step 1: analyze"))
    assert proc.reasoning == "Step 1: analyze"


@pytest.mark.asyncio
async def test_optimization_progress_captured() -> None:
    proc, _ = _make_processor()
    await proc.on_event(
        "optimization_progress",
        optimization_progress_event("opt-1", "running", 3, 10),
    )
    assert proc.optimization_progress is not None
    assert proc.optimization_progress["status"] == "running"
    assert proc.optimization_progress["currentTrial"] == 3


@pytest.mark.asyncio
async def test_graph_snapshot_persists_to_repo() -> None:
    repo = FakeStrategyRepo()
    sid = uuid4()
    proc, _ = _make_processor(repo=repo, strategy_id=sid)
    await proc.on_event(
        "graph_snapshot",
        graph_snapshot_event(str(sid), name="My Strategy", record_type="gene"),
    )
    assert str(sid) in proc.latest_graph_snapshots
    # Should have persisted via repo.update
    assert len(repo.updated) >= 1


@pytest.mark.asyncio
async def test_graph_plan_stores_plan_data() -> None:
    proc, _ = _make_processor()
    gid = str(uuid4())
    await proc.on_event(
        "graph_plan",
        graph_plan_event(gid, plan={"steps": []}, name="Plan A"),
    )
    assert gid in proc.latest_plans
    assert proc.latest_plans[gid]["name"] == "Plan A"


@pytest.mark.asyncio
async def test_strategy_meta_updates_repo() -> None:
    repo = FakeStrategyRepo()
    sid = uuid4()
    proc, _ = _make_processor(repo=repo, strategy_id=sid)
    await proc.on_event(
        "strategy_meta",
        strategy_meta_event(str(sid), name="New Name", record_type="gene"),
    )
    assert len(repo.updated) == 1
    assert repo.updated[0]["name"] == "New Name"
    assert repo.updated[0]["record_type"] == "gene"


@pytest.mark.asyncio
async def test_graph_cleared_resets_strategy() -> None:
    repo = FakeStrategyRepo()
    sid = uuid4()
    proc, _ = _make_processor(repo=repo, strategy_id=sid)
    await proc.on_event("graph_cleared", graph_cleared_event(str(sid)))
    assert len(repo.updated) == 1
    assert repo.updated[0]["title"] == "Draft Strategy"
    assert repo.updated[0]["wdk_strategy_id"] is None


@pytest.mark.asyncio
async def test_subkani_lifecycle_tracked() -> None:
    proc, _ = _make_processor()
    await proc.on_event("subkani_task_start", subkani_task_start_event("task-1"))
    assert proc.subkani_status["task-1"] == "running"

    await proc.on_event(
        "subkani_tool_call_start",
        subkani_tool_call_start_event("task-1", "sc1", "search"),
    )
    assert len(proc.subkani_calls["task-1"]) == 1

    await proc.on_event(
        "subkani_tool_call_end",
        subkani_tool_call_end_event("task-1", "sc1", "ok"),
    )
    assert proc.subkani_calls_by_id["sc1"][1]["result"] == "ok"

    await proc.on_event("subkani_task_end", subkani_task_end_event("task-1", "done"))
    assert proc.subkani_status["task-1"] == "done"


@pytest.mark.asyncio
async def test_finalize_persists_messages() -> None:
    repo = FakeStrategyRepo()
    proc, _ = _make_processor(repo=repo)
    await proc.on_event("assistant_message", assistant_message_event("Done!"))
    await proc.finalize()
    assert len(repo.messages) == 1
    assert repo.messages[0]["content"] == "Done!"
    assert repo.messages[0]["role"] == "assistant"


@pytest.mark.asyncio
async def test_finalize_attaches_metadata_to_last_message() -> None:
    repo = FakeStrategyRepo()
    proc, _ = _make_processor(repo=repo)
    await proc.on_event("assistant_message", assistant_message_event("First"))
    await proc.on_event("assistant_message", assistant_message_event("Second"))
    await proc.on_event("citations", citations_event([{"id": "c1"}]))
    await proc.on_event("planning_artifact", planning_artifact_event("a1"))
    await proc.on_event("reasoning", reasoning_event("Think"))
    await proc.on_event(
        "optimization_progress", optimization_progress_event("opt-1", "completed", 5, 5)
    )
    await proc.finalize()
    assert len(repo.messages) == 2
    # First message has no metadata
    assert repo.messages[0].get("citations") is None
    # Last message has all metadata
    last = repo.messages[1]
    assert last["citations"] == [{"id": "c1"}]
    assert last["planningArtifacts"][0]["id"] == "a1"
    assert last["reasoning"] == "Think"
    assert last["optimizationProgress"]["status"] == "completed"


@pytest.mark.asyncio
async def test_finalize_empty_stream_graceful() -> None:
    repo = FakeStrategyRepo()
    proc, _ = _make_processor(repo=repo)
    extra = await proc.finalize()
    assert extra == []
    assert len(repo.messages) == 0
    assert len(repo.thinking_cleared) == 1


@pytest.mark.asyncio
async def test_finalize_adds_done_message_when_only_tool_calls() -> None:
    repo = FakeStrategyRepo()
    proc, _ = _make_processor(repo=repo)
    await proc.on_event("tool_call_start", tool_call_start_event("t1", "search"))
    await proc.on_event("tool_call_end", tool_call_end_event("t1", "ok"))
    await proc.finalize()
    assert len(repo.messages) == 1
    assert repo.messages[0]["content"] == "Done."


@pytest.mark.asyncio
async def test_error_handler_clears_thinking_and_returns_sse_error() -> None:
    repo = FakeStrategyRepo()
    proc, _ = _make_processor(repo=repo)
    result = await proc.handle_exception(ValueError("Boom"))
    assert "error" in result
    assert "Boom" in result
    assert len(repo.thinking_cleared) == 1

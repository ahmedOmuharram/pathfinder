"""Tier 1 + concurrency integration tests for the operations system.

Covers the critical production paths that test_http_operations.py smoke tests
don't cover:

- Full operation lifecycle (create → events → subscribe → terminal event)
- SSE frame format verification (id/event/data fields)
- Cursor-based reconnection via lastEventId
- Cancellation → CancelledError → message_end → status update
- Producer error → error event + message_end → status=failed
- Orphan cleanup and stale operation expiration
- Concurrent subscribers on the same operation
- Operation ID filtering on shared chat streams
- Authorization: experiment ops exempt, chat ops owner-only
- All status transitions and their effect on list_active

WDK alignment note: WDK has NO async operations system (all synchronous).
PathFinder's operation layer is a justified extension that sits *above* WDK.
These tests verify the extension layer is correct, while WDK API calls
(step creation, strategy CRUD) remain synchronous and field-name-aligned
with WDK (verified in test_wdk_strategy_api.py and test_veupathdb_steps.py).
"""

import asyncio
import contextlib
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
import jwt
import pytest
from sqlalchemy import select, update

from veupath_chatbot.persistence.models import Operation, Stream, StreamProjection, User
from veupath_chatbot.persistence.repositories.stream import StreamRepository
from veupath_chatbot.persistence.session import async_session_factory
from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.redis import get_redis
from veupath_chatbot.services.chat import orchestrator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_user_id(authed_client: httpx.AsyncClient) -> UUID:
    """Extract user_id from the authed client's JWT cookie."""
    token = authed_client.cookies.get("pathfinder-auth")
    assert token is not None
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.api_secret_key,
        algorithms=["HS256"],
        options={"require": ["exp", "sub"]},
    )
    return UUID(payload["sub"])


async def _create_stream_and_operation(
    authed_client: httpx.AsyncClient,
    *,
    op_type: str = "chat",
    status: str = "active",
) -> tuple[UUID, str, UUID]:
    """Create a stream + projection + operation.

    Returns ``(stream_id, operation_id, user_id)``.
    """
    user_id = _extract_user_id(authed_client)

    async with async_session_factory() as session:
        stream_id = uuid4()
        session.add(Stream(id=stream_id, user_id=user_id, site_id="plasmodb"))
        await session.flush()

        session.add(
            StreamProjection(stream_id=stream_id, name="Test", site_id="plasmodb")
        )
        await session.flush()

        op_id = f"op_{uuid4().hex[:12]}"
        session.add(
            Operation(
                operation_id=op_id,
                stream_id=stream_id,
                type=op_type,
                status=status,
            )
        )
        await session.commit()

    return stream_id, op_id, user_id


async def _seed_events(
    stream_id: UUID,
    op_id: str,
    events: list[tuple[str, dict[str, object]]],
) -> list[str]:
    """Seed events into Redis and return their entry IDs."""
    redis = get_redis()
    stream_key = f"stream:{stream_id}"
    entry_ids: list[str] = []
    for event_type, data in events:
        entry_id_raw = await redis.xadd(
            stream_key,
            {
                b"type": event_type.encode(),
                b"data": json.dumps(data).encode(),
                b"op": op_id.encode(),
            },
        )
        decoded = (
            entry_id_raw.decode()
            if isinstance(entry_id_raw, bytes)
            else str(entry_id_raw)
        )
        entry_ids.append(decoded)
    return entry_ids


def _parse_sse_events(text: str) -> list[dict[str, object]]:
    """Parse raw SSE text into structured event dicts.

    Each event is ``{"id": str, "event": str, "data": parsed_json}``.
    Keepalive comments (``:``) are skipped.
    """
    events: list[dict[str, object]] = []
    current: dict[str, str] = {}
    for line in text.split("\n"):
        if line.startswith("id: "):
            current["id"] = line[4:]
        elif line.startswith("event: "):
            current["event"] = line[7:]
        elif line.startswith("data: "):
            current["data"] = line[6:]
        elif line == "" and current:
            if "event" in current:
                parsed: dict[str, object] = {}
                parsed["event"] = current["event"]
                if "id" in current:
                    parsed["id"] = current["id"]
                if "data" in current:
                    try:
                        parsed["data"] = json.loads(current["data"])
                    except json.JSONDecodeError:
                        parsed["data"] = current["data"]
                events.append(parsed)
            current = {}
    return events


# ---------------------------------------------------------------------------
# Full Lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subscribe_receives_events_in_order(
    authed_client: httpx.AsyncClient,
) -> None:
    """Subscriber receives all events in the order they were emitted."""
    stream_id, op_id, _ = await _create_stream_and_operation(authed_client)

    events = [
        ("assistant_delta", {"text": "Hello"}),
        ("assistant_delta", {"text": " world"}),
        ("assistant_message", {"messageId": "msg1", "content": "Hello world"}),
        ("message_end", {"promptTokens": 10, "completionTokens": 5}),
    ]
    await _seed_events(stream_id, op_id, events)

    resp = await authed_client.get(f"/api/v1/operations/{op_id}/subscribe")
    assert resp.status_code == 200

    sse = _parse_sse_events(resp.text)
    assert len(sse) == 4
    assert [e["event"] for e in sse] == [
        "assistant_delta",
        "assistant_delta",
        "assistant_message",
        "message_end",
    ]
    # Verify data payloads round-tripped correctly
    assert sse[0]["data"]["text"] == "Hello"
    assert sse[1]["data"]["text"] == " world"
    assert sse[2]["data"]["content"] == "Hello world"
    assert sse[3]["data"]["promptTokens"] == 10


@pytest.mark.asyncio
async def test_sse_frames_include_id_event_data_fields(
    authed_client: httpx.AsyncClient,
) -> None:
    """Every SSE frame must include id, event, and data fields."""
    stream_id, op_id, _ = await _create_stream_and_operation(authed_client)

    entry_ids = await _seed_events(
        stream_id,
        op_id,
        [
            ("assistant_delta", {"text": "hi"}),
            ("message_end", {}),
        ],
    )

    resp = await authed_client.get(f"/api/v1/operations/{op_id}/subscribe")
    sse = _parse_sse_events(resp.text)

    for event in sse:
        assert "id" in event, f"Missing 'id' in event: {event}"
        assert "event" in event, f"Missing 'event' in event: {event}"
        assert "data" in event, f"Missing 'data' in event: {event}"

    # Entry IDs must match what Redis returned
    assert sse[0]["id"] == entry_ids[0]
    assert sse[1]["id"] == entry_ids[1]


@pytest.mark.asyncio
async def test_completed_operation_excluded_from_active(
    authed_client: httpx.AsyncClient,
) -> None:
    """Completed operations must not appear in list_active."""
    _, op_id, _ = await _create_stream_and_operation(authed_client)

    # Confirm it's active
    resp = await authed_client.get("/api/v1/operations/active")
    assert any(o["operationId"] == op_id for o in resp.json())

    # Mark completed
    async with async_session_factory() as session:
        repo = StreamRepository(session)
        await repo.complete_operation(op_id)
        await session.commit()

    # Confirm excluded
    resp = await authed_client.get("/api/v1/operations/active")
    assert not any(o["operationId"] == op_id for o in resp.json())


@pytest.mark.asyncio
async def test_all_terminal_status_transitions(
    authed_client: httpx.AsyncClient,
) -> None:
    """All terminal statuses (completed, failed, cancelled) exclude from active
    and record completed_at timestamp."""
    for target_status in ("completed", "failed", "cancelled"):
        _, op_id, _ = await _create_stream_and_operation(authed_client)

        async with async_session_factory() as session:
            repo = StreamRepository(session)
            if target_status == "completed":
                await repo.complete_operation(op_id)
            elif target_status == "failed":
                await repo.fail_operation(op_id)
            else:
                await repo.cancel_operation(op_id)
            await session.commit()

        # Verify DB state
        async with async_session_factory() as session:
            result = await session.execute(
                select(Operation).where(Operation.operation_id == op_id)
            )
            op = result.scalar_one()
            assert op.status == target_status
            assert op.completed_at is not None

        # Verify excluded from active list
        resp = await authed_client.get("/api/v1/operations/active")
        assert not any(o["operationId"] == op_id for o in resp.json())


@pytest.mark.asyncio
async def test_terminal_event_stops_stream(
    authed_client: httpx.AsyncClient,
) -> None:
    """Subscriber stops reading after any terminal event type.

    Terminal events: message_end, experiment_end, batch_complete, batch_error,
    benchmark_complete, benchmark_error, seed_complete.
    """
    for terminal in (
        "message_end",
        "batch_complete",
        "batch_error",
        "benchmark_complete",
        "benchmark_error",
        "seed_complete",
    ):
        stream_id, op_id, _ = await _create_stream_and_operation(authed_client)
        await _seed_events(
            stream_id,
            op_id,
            [
                ("assistant_delta", {"text": "before"}),
                (terminal, {}),
                # Events after the terminal should NOT be delivered
                ("assistant_delta", {"text": "after_should_not_appear"}),
            ],
        )

        resp = await authed_client.get(f"/api/v1/operations/{op_id}/subscribe")
        sse = _parse_sse_events(resp.text)

        event_types = [e["event"] for e in sse]
        assert terminal in event_types, f"Missing terminal event: {terminal}"
        assert "after_should_not_appear" not in str(sse), (
            f"Events after {terminal} should not be delivered"
        )


# ---------------------------------------------------------------------------
# Reconnection via lastEventId
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reconnect_resumes_from_last_event_id(
    authed_client: httpx.AsyncClient,
) -> None:
    """Subscriber with lastEventId only receives events after that cursor."""
    stream_id, op_id, _ = await _create_stream_and_operation(authed_client)

    events = [
        ("assistant_delta", {"text": "first"}),
        ("assistant_delta", {"text": "second"}),
        ("assistant_message", {"content": "full"}),
        ("message_end", {}),
    ]
    entry_ids = await _seed_events(stream_id, op_id, events)

    # Reconnect after the second event — should only see events 3 and 4
    resp = await authed_client.get(
        f"/api/v1/operations/{op_id}/subscribe",
        params={"lastEventId": entry_ids[1]},
    )
    assert resp.status_code == 200

    sse = _parse_sse_events(resp.text)
    assert len(sse) == 2
    assert sse[0]["event"] == "assistant_message"
    assert sse[1]["event"] == "message_end"


@pytest.mark.asyncio
async def test_full_replay_without_last_event_id(
    authed_client: httpx.AsyncClient,
) -> None:
    """Without lastEventId, subscriber receives ALL events from the beginning."""
    stream_id, op_id, _ = await _create_stream_and_operation(authed_client)

    events = [
        ("assistant_delta", {"text": "a"}),
        ("assistant_delta", {"text": "b"}),
        ("assistant_delta", {"text": "c"}),
        ("message_end", {}),
    ]
    await _seed_events(stream_id, op_id, events)

    resp = await authed_client.get(f"/api/v1/operations/{op_id}/subscribe")
    sse = _parse_sse_events(resp.text)
    assert len(sse) == 4


@pytest.mark.asyncio
async def test_reconnect_at_last_event_receives_only_terminal(
    authed_client: httpx.AsyncClient,
) -> None:
    """Reconnecting at the penultimate event receives only the terminal."""
    stream_id, op_id, _ = await _create_stream_and_operation(authed_client)

    events = [
        ("assistant_delta", {"text": "content"}),
        ("assistant_message", {"content": "full text"}),
        ("message_end", {}),
    ]
    entry_ids = await _seed_events(stream_id, op_id, events)

    # Reconnect after the assistant_message — only message_end remains
    resp = await authed_client.get(
        f"/api/v1/operations/{op_id}/subscribe",
        params={"lastEventId": entry_ids[1]},
    )
    sse = _parse_sse_events(resp.text)
    assert len(sse) == 1
    assert sse[0]["event"] == "message_end"


# ---------------------------------------------------------------------------
# Cancellation flow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_running_task_returns_true() -> None:
    """cancel_chat_operation finds the task in _active_tasks and cancels it."""
    cancelled_event = asyncio.Event()

    async def slow_producer() -> None:
        try:
            await asyncio.sleep(100)
        except asyncio.CancelledError:
            cancelled_event.set()
            raise

    task = asyncio.create_task(slow_producer())
    op_id = "op_cancel_test1"
    orchestrator._active_tasks[op_id] = task
    task.add_done_callback(lambda _: orchestrator._active_tasks.pop(op_id, None))

    # Let the task reach its first await (asyncio.sleep) before cancelling.
    # In production the HTTP response is sent before cancel arrives, so the
    # producer always has at least one loop iteration to start.
    await asyncio.sleep(0)

    try:
        result = await orchestrator.cancel_chat_operation(op_id)
        assert result is True

        assert cancelled_event.is_set(), (
            "CancelledError was never delivered to the task"
        )
        assert task.done()
        assert op_id not in orchestrator._active_tasks
    finally:
        if not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


@pytest.mark.asyncio
async def test_cancel_nonexistent_operation_returns_false() -> None:
    """Cancelling a non-existent operation returns False."""
    result = await orchestrator.cancel_chat_operation("op_does_not_exist")
    assert result is False


@pytest.mark.asyncio
async def test_cancel_done_task_cleaned_from_registry() -> None:
    """After a task completes normally, it's removed from _active_tasks."""

    async def fast_task() -> None:
        pass

    op_id = "op_cleanup_test"
    task = asyncio.create_task(fast_task())
    orchestrator._active_tasks[op_id] = task
    task.add_done_callback(lambda _: orchestrator._active_tasks.pop(op_id, None))

    # Wait for task to complete
    await task

    assert op_id not in orchestrator._active_tasks
    # Cancelling a completed task should return False
    result = await orchestrator.cancel_chat_operation(op_id)
    assert result is False


@pytest.mark.asyncio
async def test_handle_cancellation_emits_message_end_and_sets_status(
    authed_client: httpx.AsyncClient,
) -> None:
    """_handle_cancellation emits message_end to Redis and sets status=cancelled."""
    stream_id, op_id, _ = await _create_stream_and_operation(authed_client)

    redis = get_redis()
    async with async_session_factory() as session:
        stream_repo = StreamRepository(session)
        await orchestrator._handle_cancellation(
            redis=redis,
            session=session,
            stream_id_str=str(stream_id),
            operation_id=op_id,
            stream_repo=stream_repo,
        )

    # Verify message_end was emitted to Redis
    stream_key = f"stream:{stream_id}"
    entries = await redis.xrange(stream_key)
    event_types = [e[1][b"type"].decode() for e in entries]
    assert "message_end" in event_types

    # Verify operation status is "cancelled"
    async with async_session_factory() as session:
        result = await session.execute(
            select(Operation.status).where(Operation.operation_id == op_id)
        )
        assert result.scalar_one() == "cancelled"


@pytest.mark.asyncio
async def test_handle_error_emits_error_and_message_end(
    authed_client: httpx.AsyncClient,
) -> None:
    """_handle_error emits error + message_end and sets status=failed."""
    stream_id, op_id, _ = await _create_stream_and_operation(authed_client)

    redis = get_redis()
    async with async_session_factory() as session:
        stream_repo = StreamRepository(session)
        await orchestrator._handle_error(
            error=RuntimeError("LLM provider timeout"),
            redis=redis,
            session=session,
            stream_id_str=str(stream_id),
            operation_id=op_id,
            stream_repo=stream_repo,
        )
        await session.commit()

    # Verify both error and message_end were emitted
    stream_key = f"stream:{stream_id}"
    entries = await redis.xrange(stream_key)
    event_types = [e[1][b"type"].decode() for e in entries]
    assert "error" in event_types
    assert "message_end" in event_types
    # error must come BEFORE message_end
    assert event_types.index("error") < event_types.index("message_end")

    # Verify the error event contains the error message
    error_entries = [e for e in entries if e[1][b"type"] == b"error"]
    error_data = json.loads(error_entries[0][1][b"data"])
    assert error_data["error"] == "An internal error occurred"

    # Verify operation status is "failed"
    async with async_session_factory() as session:
        result = await session.execute(
            select(Operation.status).where(Operation.operation_id == op_id)
        )
        assert result.scalar_one() == "failed"


# ---------------------------------------------------------------------------
# Orphan cleanup & stale operation expiration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_orphaned_operations_marked_failed_via_cleanup(
    authed_client: httpx.AsyncClient,
) -> None:
    """Startup cleanup marks all 'active' operations as 'failed'.

    Simulates the Docker-rebuild / crash case where the producer task
    died without marking the operation complete.
    """
    # Create two active operations
    _, op_id_1, _ = await _create_stream_and_operation(authed_client)
    _, op_id_2, _ = await _create_stream_and_operation(authed_client)

    # Run the same cleanup logic that main.py lifespan runs
    async with async_session_factory() as session:
        repo = StreamRepository(session)
        orphaned = await repo.list_active_operations()
        assert len(orphaned) >= 2
        for op in orphaned:
            await repo.fail_operation(op.operation_id)
        await session.commit()

    # Both operations should now be "failed"
    async with async_session_factory() as session:
        for op_id in (op_id_1, op_id_2):
            result = await session.execute(
                select(Operation).where(Operation.operation_id == op_id)
            )
            op = result.scalar_one()
            assert op.status == "failed"
            assert op.completed_at is not None

    # list_active should return empty
    resp = await authed_client.get("/api/v1/operations/active")
    assert resp.json() == []


@pytest.mark.asyncio
async def test_expire_stale_operations_marks_old_active_as_failed(
    authed_client: httpx.AsyncClient,
) -> None:
    """expire_stale_operations marks operations active longer than max_age
    as failed, while leaving recent operations untouched."""
    # Create two operations
    _, stale_op_id, _ = await _create_stream_and_operation(authed_client)
    _, fresh_op_id, _ = await _create_stream_and_operation(authed_client)

    # Backdate the first to simulate a stale operation (created an hour ago)
    async with async_session_factory() as session:
        await session.execute(
            update(Operation)
            .where(Operation.operation_id == stale_op_id)
            .values(created_at=datetime(2020, 1, 1, tzinfo=UTC))
        )
        await session.commit()

    # Expire stale operations (max_age=60 seconds)
    async with async_session_factory() as session:
        repo = StreamRepository(session)
        expired_count = await repo.expire_stale_operations(max_age_seconds=60)
        await session.commit()

    assert expired_count == 1

    # Stale operation should be failed
    async with async_session_factory() as session:
        result = await session.execute(
            select(Operation).where(Operation.operation_id == stale_op_id)
        )
        op = result.scalar_one()
        assert op.status == "failed"
        assert op.completed_at is not None

    # Fresh operation should still be active
    async with async_session_factory() as session:
        result = await session.execute(
            select(Operation).where(Operation.operation_id == fresh_op_id)
        )
        op = result.scalar_one()
        assert op.status == "active"
        assert op.completed_at is None

    # list_active should only show the fresh operation
    resp = await authed_client.get("/api/v1/operations/active")
    ops = resp.json()
    assert any(o["operationId"] == fresh_op_id for o in ops)
    assert not any(o["operationId"] == stale_op_id for o in ops)


# ---------------------------------------------------------------------------
# Concurrency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_subscribers_both_receive_all_events(
    authed_client: httpx.AsyncClient,
) -> None:
    """Two concurrent subscribers to the same operation both receive all events.

    Redis Streams XREAD is non-destructive — multiple independent readers
    can read the same entries without interference.
    """
    stream_id, op_id, _ = await _create_stream_and_operation(authed_client)
    await _seed_events(
        stream_id,
        op_id,
        [
            ("assistant_delta", {"text": "hello"}),
            ("assistant_message", {"content": "hello"}),
            ("message_end", {}),
        ],
    )

    # Subscribe twice concurrently
    resp1, resp2 = await asyncio.gather(
        authed_client.get(f"/api/v1/operations/{op_id}/subscribe"),
        authed_client.get(f"/api/v1/operations/{op_id}/subscribe"),
    )

    sse1 = _parse_sse_events(resp1.text)
    sse2 = _parse_sse_events(resp2.text)

    # Both subscribers should receive all 3 events
    assert len(sse1) == 3
    assert len(sse2) == 3
    assert [e["event"] for e in sse1] == [
        "assistant_delta",
        "assistant_message",
        "message_end",
    ]
    assert [e["event"] for e in sse2] == [
        "assistant_delta",
        "assistant_message",
        "message_end",
    ]


@pytest.mark.asyncio
async def test_shared_stream_operation_id_filtering(
    authed_client: httpx.AsyncClient,
) -> None:
    """On a shared chat stream, subscriber only sees events for their operation.

    Chat operations share a stream keyed by stream_id. Events from
    different operations on the same stream must be filtered by operation_id.
    """
    user_id = _extract_user_id(authed_client)

    # Create ONE stream with TWO operations
    async with async_session_factory() as session:
        stream_id = uuid4()
        session.add(Stream(id=stream_id, user_id=user_id, site_id="plasmodb"))
        await session.flush()
        session.add(
            StreamProjection(stream_id=stream_id, name="Shared", site_id="plasmodb")
        )
        await session.flush()

        op_id_a = f"op_{uuid4().hex[:12]}"
        op_id_b = f"op_{uuid4().hex[:12]}"
        session.add(
            Operation(
                operation_id=op_id_a,
                stream_id=stream_id,
                type="chat",
                status="active",
            )
        )
        session.add(
            Operation(
                operation_id=op_id_b,
                stream_id=stream_id,
                type="chat",
                status="active",
            )
        )
        await session.commit()

    # Seed interleaved events for BOTH operations on the SAME Redis stream
    redis = get_redis()
    stream_key = f"stream:{stream_id}"

    await redis.xadd(
        stream_key,
        {
            b"type": b"assistant_delta",
            b"data": json.dumps({"text": "op_a event"}).encode(),
            b"op": op_id_a.encode(),
        },
    )
    await redis.xadd(
        stream_key,
        {
            b"type": b"assistant_delta",
            b"data": json.dumps({"text": "op_b event"}).encode(),
            b"op": op_id_b.encode(),
        },
    )
    await redis.xadd(
        stream_key,
        {
            b"type": b"assistant_delta",
            b"data": json.dumps({"text": "op_a second"}).encode(),
            b"op": op_id_a.encode(),
        },
    )
    await redis.xadd(
        stream_key,
        {
            b"type": b"message_end",
            b"data": b"{}",
            b"op": op_id_a.encode(),
        },
    )

    # Subscribe to op_a — should only see op_a events
    resp = await authed_client.get(f"/api/v1/operations/{op_id_a}/subscribe")
    sse = _parse_sse_events(resp.text)

    # Should see: op_a delta, op_a second delta, message_end (3 events)
    # op_b delta should be filtered out
    assert len(sse) == 3
    assert sse[0]["data"]["text"] == "op_a event"
    assert sse[1]["data"]["text"] == "op_a second"
    assert sse[2]["event"] == "message_end"


@pytest.mark.asyncio
async def test_multiple_active_operations_same_stream(
    authed_client: httpx.AsyncClient,
) -> None:
    """Multiple active operations on the same stream are all listed."""
    user_id = _extract_user_id(authed_client)

    async with async_session_factory() as session:
        stream_id = uuid4()
        session.add(Stream(id=stream_id, user_id=user_id, site_id="plasmodb"))
        await session.flush()
        session.add(
            StreamProjection(stream_id=stream_id, name="Multi", site_id="plasmodb")
        )
        await session.flush()

        op_ids = []
        for _ in range(3):
            op_id = f"op_{uuid4().hex[:12]}"
            session.add(
                Operation(
                    operation_id=op_id,
                    stream_id=stream_id,
                    type="chat",
                    status="active",
                )
            )
            op_ids.append(op_id)
        await session.commit()

    resp = await authed_client.get(
        "/api/v1/operations/active", params={"streamId": str(stream_id)}
    )
    ops = resp.json()
    returned_ids = {o["operationId"] for o in ops}
    assert set(op_ids).issubset(returned_ids)


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_experiment_ops_exempt_from_stream_ownership(
    authed_client: httpx.AsyncClient,
) -> None:
    """Experiment operations are accessible regardless of stream ownership.

    The operations router exempts experiment/batch/benchmark types from
    the stream ownership check, since experiment streams use a shared
    synthetic stream.
    """
    # Create a stream owned by a DIFFERENT user
    other_user_id = uuid4()
    async with async_session_factory() as session:
        session.add(User(id=other_user_id))
        stream_id = uuid4()
        session.add(Stream(id=stream_id, user_id=other_user_id, site_id="plasmodb"))
        await session.flush()
        session.add(
            StreamProjection(stream_id=stream_id, name="Other", site_id="plasmodb")
        )
        await session.flush()

        op_id = f"op_{uuid4().hex[:12]}"
        session.add(
            Operation(
                operation_id=op_id,
                stream_id=stream_id,
                type="experiment",
                status="active",
            )
        )
        await session.commit()

    # Seed event on experiment's dedicated stream (op: prefix, not stream: prefix)
    redis = get_redis()
    await redis.xadd(
        f"op:{op_id}",
        {
            b"type": b"experiment_end",
            b"data": b"{}",
            b"op": op_id.encode(),
        },
    )

    # Current user (not stream owner) should still be able to subscribe
    resp = await authed_client.get(f"/api/v1/operations/{op_id}/subscribe")
    assert resp.status_code == 200
    sse = _parse_sse_events(resp.text)
    assert any(e["event"] == "experiment_end" for e in sse)


@pytest.mark.asyncio
async def test_chat_ops_forbidden_for_non_owner(
    authed_client: httpx.AsyncClient,
) -> None:
    """Chat operations require stream ownership — non-owners get 403."""
    other_user_id = uuid4()
    async with async_session_factory() as session:
        session.add(User(id=other_user_id))
        stream_id = uuid4()
        session.add(Stream(id=stream_id, user_id=other_user_id, site_id="plasmodb"))
        await session.flush()
        session.add(
            StreamProjection(stream_id=stream_id, name="Other", site_id="plasmodb")
        )
        await session.flush()

        op_id = f"op_{uuid4().hex[:12]}"
        session.add(
            Operation(
                operation_id=op_id,
                stream_id=stream_id,
                type="chat",
                status="active",
            )
        )
        await session.commit()

    resp = await authed_client.get(f"/api/v1/operations/{op_id}/subscribe")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_cancel_forbidden_for_non_owner(
    authed_client: httpx.AsyncClient,
) -> None:
    """Cancel on a non-owned chat operation returns 403."""
    other_user_id = uuid4()
    async with async_session_factory() as session:
        session.add(User(id=other_user_id))
        stream_id = uuid4()
        session.add(Stream(id=stream_id, user_id=other_user_id, site_id="plasmodb"))
        await session.flush()
        session.add(
            StreamProjection(stream_id=stream_id, name="Other", site_id="plasmodb")
        )
        await session.flush()

        op_id = f"op_{uuid4().hex[:12]}"
        session.add(
            Operation(
                operation_id=op_id,
                stream_id=stream_id,
                type="chat",
                status="active",
            )
        )
        await session.commit()

    resp = await authed_client.post(f"/api/v1/operations/{op_id}/cancel")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_malformed_json_in_event_data_does_not_crash(
    authed_client: httpx.AsyncClient,
) -> None:
    """Malformed JSON in Redis event data is handled gracefully."""
    stream_id, op_id, _ = await _create_stream_and_operation(authed_client)

    redis = get_redis()
    stream_key = f"stream:{stream_id}"

    # Add event with invalid JSON
    await redis.xadd(
        stream_key,
        {
            b"type": b"assistant_delta",
            b"data": b"not-valid-json{{{",
            b"op": op_id.encode(),
        },
    )
    # Add terminal event
    await redis.xadd(
        stream_key,
        {
            b"type": b"message_end",
            b"data": b"{}",
            b"op": op_id.encode(),
        },
    )

    resp = await authed_client.get(f"/api/v1/operations/{op_id}/subscribe")
    assert resp.status_code == 200

    sse = _parse_sse_events(resp.text)
    # Malformed event should still be delivered (with empty data fallback)
    assert len(sse) == 2
    assert sse[0]["event"] == "assistant_delta"
    assert sse[0]["data"] == {}  # Fallback for malformed JSON
    assert sse[1]["event"] == "message_end"


@pytest.mark.asyncio
async def test_events_without_op_field_are_visible_to_all(
    authed_client: httpx.AsyncClient,
) -> None:
    """Events with empty op field pass through the operation filter.

    This covers legacy events or events emitted without operation context.
    """
    stream_id, op_id, _ = await _create_stream_and_operation(authed_client)

    redis = get_redis()
    stream_key = f"stream:{stream_id}"

    # Event with empty op field (matches "if event_op and event_op != operation_id")
    await redis.xadd(
        stream_key,
        {
            b"type": b"assistant_delta",
            b"data": json.dumps({"text": "legacy"}).encode(),
            b"op": b"",
        },
    )
    await redis.xadd(
        stream_key,
        {
            b"type": b"message_end",
            b"data": b"{}",
            b"op": op_id.encode(),
        },
    )

    resp = await authed_client.get(f"/api/v1/operations/{op_id}/subscribe")
    sse = _parse_sse_events(resp.text)

    # Empty-op event should pass the filter
    assert len(sse) == 2
    assert sse[0]["data"]["text"] == "legacy"

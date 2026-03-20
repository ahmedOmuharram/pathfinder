"""Integration tests for the operations router (subscribe, cancel, list_active)."""

import json
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import httpx
import jwt
import pytest

import veupath_chatbot.persistence.session as session_module
from veupath_chatbot.persistence.models import Operation, Stream, StreamProjection
from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.redis import get_redis

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_stream_and_operation(
    authed_client: httpx.AsyncClient,
    *,
    op_type: str = "chat",
    status: str = "active",
) -> tuple[UUID, str, UUID]:
    """Create a stream + operation directly in the DB.

    Returns (stream_id, operation_id, user_id).
    """
    # Extract user_id from the authed client cookie
    token = authed_client.cookies.get("pathfinder-auth")
    assert token is not None

    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.api_secret_key,
        algorithms=["HS256"],
        options={"require": ["exp", "sub"]},
    )
    user_id = UUID(payload["sub"])

    async with session_module.async_session_factory() as session:
        stream_id = uuid4()
        stream = Stream(id=stream_id, user_id=user_id, site_id="plasmodb")
        session.add(stream)
        await session.flush()

        # Create projection (needed for joins)
        proj = StreamProjection(stream_id=stream_id, name="Test", site_id="plasmodb")
        session.add(proj)
        await session.flush()

        # Create operation
        op_id = uuid4().hex
        op = Operation(
            operation_id=op_id,
            stream_id=stream_id,
            type=op_type,
            status=status,
        )
        session.add(op)
        await session.commit()

    return stream_id, op_id, user_id


# ---------------------------------------------------------------------------
# Auth enforcement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subscribe_requires_auth(client: httpx.AsyncClient) -> None:
    """Unauthenticated subscribe should return 401."""
    resp = await client.get("/api/v1/operations/fake-op-id/subscribe")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_cancel_requires_auth(client: httpx.AsyncClient) -> None:
    """Unauthenticated cancel should return 401."""
    resp = await client.post("/api/v1/operations/fake-op-id/cancel")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_active_requires_auth(client: httpx.AsyncClient) -> None:
    """Unauthenticated list_active should return 401."""
    resp = await client.get("/api/v1/operations/active")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# list_active
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_active_empty(authed_client: httpx.AsyncClient) -> None:
    """No active operations should return empty list."""
    resp = await authed_client.get("/api/v1/operations/active")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_active_returns_operations(authed_client: httpx.AsyncClient) -> None:
    """Active operations should appear in the list."""
    stream_id, op_id, _user_id = await _create_stream_and_operation(authed_client)

    resp = await authed_client.get("/api/v1/operations/active")
    assert resp.status_code == 200
    ops = resp.json()
    assert len(ops) >= 1

    found = [o for o in ops if o["operationId"] == op_id]
    assert len(found) == 1
    assert found[0]["streamId"] == str(stream_id)
    assert found[0]["type"] == "chat"
    assert found[0]["status"] == "active"
    assert "createdAt" in found[0]


@pytest.mark.asyncio
async def test_list_active_filters_by_stream_id(
    authed_client: httpx.AsyncClient,
) -> None:
    """streamId filter should restrict results."""
    stream_id, op_id, _ = await _create_stream_and_operation(authed_client)

    # Filter by the actual stream — should find it
    resp = await authed_client.get(
        "/api/v1/operations/active", params={"streamId": str(stream_id)}
    )
    assert resp.status_code == 200
    ops = resp.json()
    assert any(o["operationId"] == op_id for o in ops)

    # Filter by a non-existent stream — should be empty
    resp = await authed_client.get(
        "/api/v1/operations/active", params={"streamId": str(uuid4())}
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_active_filters_by_type(authed_client: httpx.AsyncClient) -> None:
    """type filter should restrict results."""
    _stream_id, op_id, _ = await _create_stream_and_operation(
        authed_client, op_type="chat"
    )

    resp = await authed_client.get("/api/v1/operations/active", params={"type": "chat"})
    assert resp.status_code == 200
    assert any(o["operationId"] == op_id for o in resp.json())

    resp = await authed_client.get(
        "/api/v1/operations/active", params={"type": "experiment"}
    )
    assert resp.status_code == 200
    assert not any(o["operationId"] == op_id for o in resp.json())


@pytest.mark.asyncio
async def test_list_active_excludes_completed(
    authed_client: httpx.AsyncClient,
) -> None:
    """Completed operations should not appear in active list."""
    _stream_id, op_id, _ = await _create_stream_and_operation(
        authed_client, status="completed"
    )

    resp = await authed_client.get("/api/v1/operations/active")
    assert resp.status_code == 200
    assert not any(o["operationId"] == op_id for o in resp.json())


# ---------------------------------------------------------------------------
# cancel
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_not_found(authed_client: httpx.AsyncClient) -> None:
    """Cancelling a non-existent operation returns 404."""
    resp = await authed_client.post("/api/v1/operations/nonexistent/cancel")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cancel_already_completed(authed_client: httpx.AsyncClient) -> None:
    """Cancelling a completed operation returns cancelled=False."""
    _stream_id, op_id, _ = await _create_stream_and_operation(
        authed_client, status="completed"
    )

    with patch(
        "veupath_chatbot.services.chat.orchestrator.cancel_chat_operation",
        new_callable=AsyncMock,
    ) as mock_cancel:
        resp = await authed_client.post(f"/api/v1/operations/{op_id}/cancel")

    assert resp.status_code == 202
    body = resp.json()
    assert body["operationId"] == op_id
    assert body["cancelled"] is False
    mock_cancel.assert_not_called()


@pytest.mark.asyncio
async def test_cancel_active_operation(authed_client: httpx.AsyncClient) -> None:
    """Cancelling an active operation invokes cancel_chat_operation."""
    _stream_id, op_id, _ = await _create_stream_and_operation(authed_client)

    with patch(
        "veupath_chatbot.transport.http.routers.operations.cancel_chat_operation",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_cancel:
        resp = await authed_client.post(f"/api/v1/operations/{op_id}/cancel")

    assert resp.status_code == 202
    body = resp.json()
    assert body["operationId"] == op_id
    assert body["cancelled"] is True
    mock_cancel.assert_awaited_once_with(op_id)


# ---------------------------------------------------------------------------
# subscribe
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subscribe_not_found(authed_client: httpx.AsyncClient) -> None:
    """Subscribing to a non-existent operation returns 404."""
    resp = await authed_client.get("/api/v1/operations/nonexistent/subscribe")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_subscribe_returns_sse_content_type(
    authed_client: httpx.AsyncClient,
) -> None:
    """Subscribe endpoint should return text/event-stream content type.

    We seed Redis with one terminal event so the stream closes immediately.
    """
    stream_id, op_id, _ = await _create_stream_and_operation(authed_client)

    redis = get_redis()
    stream_key = f"stream:{stream_id}"
    await redis.xadd(
        stream_key,
        {
            b"type": b"message_end",
            b"data": json.dumps({"done": True}).encode(),
            b"op": op_id.encode(),
        },
    )

    resp = await authed_client.get(f"/api/v1/operations/{op_id}/subscribe")
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_subscribe_streams_events(authed_client: httpx.AsyncClient) -> None:
    """Subscribe should replay events from Redis and terminate on end event."""
    stream_id, op_id, _ = await _create_stream_and_operation(authed_client)

    redis = get_redis()
    stream_key = f"stream:{stream_id}"

    # Add a progress event
    await redis.xadd(
        stream_key,
        {
            b"type": b"assistant_delta",
            b"data": json.dumps({"text": "hello"}).encode(),
            b"op": op_id.encode(),
        },
    )
    # Add a terminal event
    await redis.xadd(
        stream_key,
        {
            b"type": b"message_end",
            b"data": json.dumps({"done": True}).encode(),
            b"op": op_id.encode(),
        },
    )

    resp = await authed_client.get(f"/api/v1/operations/{op_id}/subscribe")
    assert resp.status_code == 200

    text = resp.text
    # Should contain SSE-formatted events
    assert "event: assistant_delta" in text
    assert "event: message_end" in text
    assert '"text": "hello"' in text or '"text":"hello"' in text

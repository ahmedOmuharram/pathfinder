"""Integration coverage for structured chat metadata forwarding."""

from __future__ import annotations

from uuid import UUID

import httpx
import pytest

from pathfinder.platform.event_schemas import PipelineConfig, PipelinePhaseConfig
from pathfinder.services.chat.types import ChatTurnConfig

_MOCK_PHASE = PipelinePhaseConfig(model_id="mock/deterministic", reasoning_effort="low")
_MOCK_PIPELINE = PipelineConfig(
    scoping=_MOCK_PHASE,
    discovery=_MOCK_PHASE,
    planning=_MOCK_PHASE,
    execution=_MOCK_PHASE,
    verification=_MOCK_PHASE,
)


@pytest.mark.asyncio
async def test_chat_route_forwards_structured_metadata_to_turn_config(
    authed_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def _fake_start_chat_stream(
        *,
        message: str,
        site_id: str,
        strategy_id: UUID | None,
        context: object,
        config: ChatTurnConfig | None = None,
    ) -> tuple[str, str, str]:
        captured["message"] = message
        captured["site_id"] = site_id
        captured["strategy_id"] = strategy_id
        captured["context"] = context
        captured["config"] = config
        return ("op_test123", "11111111-1111-4111-8111-111111111111", "174")

    monkeypatch.setattr(
        "pathfinder.transport.http.routers.chat.start_chat_stream",
        _fake_start_chat_stream,
    )

    response = await authed_client.post(
        "/api/v1/chat",
        json={
            "siteId": "plasmodb",
            "message": "Please regenerate that answer.",
            "metadata": {
                "regenerateOfTraceId": "trace_123",
                "regenerateOfMessageId": "msg_456",
            },
            "pipeline": _MOCK_PIPELINE.model_dump(by_alias=True),
        },
    )

    assert response.status_code == 202
    assert response.json() == {
        "operationId": "op_test123",
        "strategyId": "11111111-1111-4111-8111-111111111111",
        "entryId": "174",
    }

    config = captured["config"]
    assert isinstance(config, ChatTurnConfig)
    assert config.metadata == {
        "regenerateOfTraceId": "trace_123",
        "regenerateOfMessageId": "msg_456",
    }

"""Typed payload models for procrastinate jobs."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from pydantic import ValidationError

from pathfinder.ai.conversation.request_body import ChatRequestBody
from pathfinder.jobs.payloads import (
    ChatTurnPayload,
    DurableTaskPayload,
)
from pathfinder.platform.context import veupathdb_auth_token_ctx


def _body() -> ChatRequestBody:
    return ChatRequestBody.model_validate(
        {
            "conversationId": str(uuid4()),
            "messages": [
                {
                    "id": str(uuid4()),
                    "role": "user",
                    "parts": [{"type": "text", "text": "hi"}],
                },
            ],
            "siteId": "plasmodb",
        },
    )


class TestChatTurnPayload:
    def test_roundtrips_with_token_intact(self) -> None:
        """Token must round-trip via JSON — this is the foot-gun SecretStr
        would hit (mask_to '**********' on model_dump_json)."""
        payload = ChatTurnPayload(
            body=_body(),
            user_id=uuid4(),
            turn_id=uuid4(),
            veupathdb_auth_token="cookie-value-abc123",
        )

        serialized = json.loads(payload.model_dump_json(by_alias=True))
        restored = ChatTurnPayload.model_validate(serialized)

        assert restored.veupathdb_auth_token == "cookie-value-abc123"
        assert restored.user_id == payload.user_id
        assert restored.turn_id == payload.turn_id

    def test_token_optional_defaults_to_none(self) -> None:
        payload = ChatTurnPayload(
            body=_body(),
            user_id=uuid4(),
            turn_id=uuid4(),
        )
        assert payload.veupathdb_auth_token is None

    def test_forbids_unknown_keys(self) -> None:
        """Payload schema is strict: extra keys must fail validation so
        we catch drift between dispatcher and receiver."""
        with pytest.raises(ValidationError):
            ChatTurnPayload.model_validate(
                {
                    "body": _body().model_dump(by_alias=True, mode="json"),
                    "user_id": str(uuid4()),
                    "turn_id": str(uuid4()),
                    "rogue_field": "x",
                },
            )

    def test_model_dump_mode_json_is_jsonable(self) -> None:
        """Procrastinate serializes args via json.dumps after psycopg Jsonb
        wrapping. model_dump(mode='json') output must pass json.dumps."""
        payload = ChatTurnPayload(
            body=_body(),
            user_id=uuid4(),
            turn_id=uuid4(),
            veupathdb_auth_token="tok",
        )
        dumped = payload.model_dump(mode="json", by_alias=True)
        json.dumps(dumped)


class TestDurableTaskPayload:
    def test_roundtrips_with_token(self) -> None:
        payload = DurableTaskPayload(
            task_id=uuid4(),
            thread_id=uuid4(),
            args={"args": [], "kwargs": {"x": 5}},
            veupathdb_auth_token="cookie-xyz",
        )
        serialized = json.loads(payload.model_dump_json(by_alias=True))
        restored = DurableTaskPayload.model_validate(serialized)

        assert restored.veupathdb_auth_token == "cookie-xyz"
        assert restored.args == {"args": [], "kwargs": {"x": 5}}

    def test_token_optional(self) -> None:
        payload = DurableTaskPayload(
            task_id=uuid4(),
            thread_id=uuid4(),
            args={},
        )
        assert payload.veupathdb_auth_token is None

    def test_forbids_unknown_keys(self) -> None:
        with pytest.raises(ValidationError):
            DurableTaskPayload.model_validate(
                {
                    "task_id": str(uuid4()),
                    "thread_id": str(uuid4()),
                    "args": {},
                    "rogue": True,
                },
            )


class TestChatTurnPayloadFromContext:
    """``from_context`` reads the current value of veupathdb_auth_token_ctx
    and returns a typed payload. Dispatchers use this at the api→worker
    boundary so the ctxvar crosses the procrastinate seam."""

    def test_captures_token_from_ctxvar(self) -> None:
        body = _body()
        user_id = uuid4()
        turn_id = uuid4()
        reset = veupathdb_auth_token_ctx.set("cookie-from-request")
        try:
            payload = ChatTurnPayload.from_context(
                body=body, user_id=user_id, turn_id=turn_id,
            )
        finally:
            veupathdb_auth_token_ctx.reset(reset)
        assert payload.veupathdb_auth_token == "cookie-from-request"
        assert payload.user_id == user_id
        assert payload.turn_id == turn_id

    def test_captures_none_when_ctxvar_unset(self) -> None:
        assert veupathdb_auth_token_ctx.get() is None
        payload = ChatTurnPayload.from_context(
            body=_body(), user_id=uuid4(), turn_id=uuid4(),
        )
        assert payload.veupathdb_auth_token is None


class TestDurableTaskPayloadFromContext:
    def test_captures_token_from_ctxvar(self) -> None:
        reset = veupathdb_auth_token_ctx.set("durable-cookie")
        try:
            payload = DurableTaskPayload.from_context(
                task_id=uuid4(),
                thread_id=uuid4(),
                args={"args": [], "kwargs": {}},
            )
        finally:
            veupathdb_auth_token_ctx.reset(reset)
        assert payload.veupathdb_auth_token == "durable-cookie"

    def test_captures_none_when_ctxvar_unset(self) -> None:
        assert veupathdb_auth_token_ctx.get() is None
        payload = DurableTaskPayload.from_context(
            task_id=uuid4(), thread_id=uuid4(), args={},
        )
        assert payload.veupathdb_auth_token is None

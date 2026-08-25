"""``ChatRequestBody`` accepts only model ids that the catalog defines."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from pathfinder.ai.conversation.request_body import ChatRequestBody
from pathfinder.ai.models.catalog import get_model_catalog

_CATALOG_MODEL_ID = get_model_catalog()[0].id


def _body(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "conversationId": str(uuid4()),
        "siteId": "plasmodb",
        "messages": [],
    }
    payload.update(overrides)
    return payload


def test_catalog_model_is_accepted() -> None:
    body = ChatRequestBody.model_validate(
        _body(phaseModels={"lead": _CATALOG_MODEL_ID})
    )

    assert body.phase_models == {"lead": _CATALOG_MODEL_ID}


def test_empty_phase_models_is_accepted() -> None:
    body = ChatRequestBody.model_validate(_body())

    assert body.phase_models == {}


def test_unknown_model_is_rejected() -> None:
    with pytest.raises(ValidationError) as excinfo:
        ChatRequestBody.model_validate(
            _body(phaseModels={"lead": "openai:not-a-real-model"})
        )

    message = str(excinfo.value)
    assert "lead" in message
    assert "openai:not-a-real-model" in message


def test_unknown_model_is_rejected_among_valid_ones() -> None:
    with pytest.raises(ValidationError) as excinfo:
        ChatRequestBody.model_validate(
            _body(
                phaseModels={
                    "lead": _CATALOG_MODEL_ID,
                    "verification": "anthropic:claude-does-not-exist",
                }
            )
        )

    message = str(excinfo.value)
    assert "verification" in message
    assert "anthropic:claude-does-not-exist" in message


def test_reasoning_effort_outside_the_literal_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ChatRequestBody.model_validate(_body(phaseReasoning={"lead": "extreme"}))


def test_a_rehydrated_assistant_message_with_turn_facts_is_accepted() -> None:
    """The protocol's reduction adds errors/aborted/finishReason; the request
    reads the thread as the client holds it, so those members parse away."""
    body = ChatRequestBody.model_validate(
        _body(
            messages=[
                {
                    "id": "m1",
                    "role": "assistant",
                    "parts": [{"type": "text", "text": "done"}],
                    "errors": [],
                    "aborted": False,
                    "finishReason": "stop",
                },
                {
                    "id": "m2",
                    "role": "user",
                    "parts": [{"type": "text", "text": "next question"}],
                },
            ]
        )
    )

    assert len(body.messages) == 2
    assert body.messages[0].role == "assistant"


def test_an_oversized_site_id_is_refused() -> None:
    with pytest.raises(ValidationError):
        ChatRequestBody.model_validate(_body(siteId="s" * 51))


def test_a_failed_tool_part_with_provider_metadata_is_accepted() -> None:
    """A live stream records resultProviderMetadata on an output-error part;
    the strict part union forbids it on resend, so it parses away."""
    body = ChatRequestBody.model_validate(
        _body(
            messages=[
                {
                    "id": "m1",
                    "role": "assistant",
                    "parts": [
                        {
                            "type": "tool-classify_user_intent",
                            "toolCallId": "c1",
                            "state": "output-error",
                            "errorText": "differential_sides caps at 2",
                            "input": {},
                            "resultProviderMetadata": {"openai": {"x": 1}},
                        }
                    ],
                },
                {
                    "id": "m2",
                    "role": "user",
                    "parts": [{"type": "text", "text": "use the first two"}],
                },
            ]
        )
    )

    assert len(body.messages) == 2

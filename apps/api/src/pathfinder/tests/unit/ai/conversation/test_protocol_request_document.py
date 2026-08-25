"""PROTOCOL.md states the body that opens a turn; ``ChatRequestBody`` is that body.

The document splits the fields into the ones any assistant on the runtime takes
and the ones this product adds. Both tables together must name every field the
model accepts, and every example on the page must validate.
"""

from __future__ import annotations

import json
import re

import pytest

from pathfinder.ai.conversation.request_body import ChatRequestBody
from pathfinder.tests.protocol_document import protocol_section

_TABLE_KEY = re.compile(r"^\| `([A-Za-z][A-Za-z0-9]*)` \|", re.MULTILINE)
_EXAMPLE = re.compile(r"#### `([^`]+)`\n\n```json\n(.*?)\n```", re.DOTALL)


def _documented_examples() -> dict[str, str]:
    return dict(_EXAMPLE.findall(protocol_section("request_examples")))


def _model_field_names() -> set[str]:
    return {field.alias or name for name, field in ChatRequestBody.model_fields.items()}


def test_the_two_field_tables_name_every_field_the_body_accepts() -> None:
    documented = set(_TABLE_KEY.findall(protocol_section("request_core"))) | set(
        _TABLE_KEY.findall(protocol_section("request_extensions")),
    )

    assert documented == _model_field_names()


def test_no_field_is_both_core_and_an_extension() -> None:
    core = set(_TABLE_KEY.findall(protocol_section("request_core")))
    extensions = set(_TABLE_KEY.findall(protocol_section("request_extensions")))

    assert core & extensions == set()


@pytest.mark.parametrize("name", ["submit-message", "approval-response"])
def test_every_documented_example_validates(name: str) -> None:
    examples = _documented_examples()

    assert name in examples, sorted(examples)
    ChatRequestBody.model_validate(json.loads(examples[name]))


def test_the_submit_example_carries_the_user_message_the_turn_answers() -> None:
    body = ChatRequestBody.model_validate(
        json.loads(_documented_examples()["submit-message"]),
    )

    assert body.is_approval_resume is False
    assert body.last_user_text != ""
    assert str(body.last_user_message_id) == body.messages[-1].id


def test_the_approval_example_resumes_a_deferred_call() -> None:
    body = ChatRequestBody.model_validate(
        json.loads(_documented_examples()["approval-response"]),
    )

    assert body.is_approval_resume is True
    assert body.prior_assistant_message_id is not None

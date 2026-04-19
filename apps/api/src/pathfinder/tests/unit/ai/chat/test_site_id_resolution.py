from __future__ import annotations

from uuid import uuid4

import pytest

from pathfinder.ai.conversation.dispatcher import resolve_site_id


def test_resolve_prefers_chat_site_id_over_body() -> None:
    assert resolve_site_id(
        chat_site_id="plasmodb",
        body_site_id="toxodb",
        conversation_id=uuid4(),
    ) == "plasmodb"


def test_resolve_falls_back_to_body_when_chat_is_none() -> None:
    assert resolve_site_id(
        chat_site_id=None,
        body_site_id="plasmodb",
        conversation_id=uuid4(),
    ) == "plasmodb"


def test_resolve_falls_back_to_body_when_chat_is_empty() -> None:
    assert resolve_site_id(
        chat_site_id="",
        body_site_id="plasmodb",
        conversation_id=uuid4(),
    ) == "plasmodb"


def test_resolve_raises_when_both_are_empty() -> None:
    conversation_id = uuid4()
    with pytest.raises(ValueError, match=f"chat {conversation_id}"):
        resolve_site_id(
            chat_site_id="",
            body_site_id="",
            conversation_id=conversation_id,
        )


def test_resolve_raises_when_both_are_none_and_empty() -> None:
    with pytest.raises(ValueError, match="site_id could not be resolved"):
        resolve_site_id(
            chat_site_id=None,
            body_site_id="",
            conversation_id=uuid4(),
        )


def test_resolve_treats_whitespace_as_empty() -> None:
    with pytest.raises(ValueError, match="site_id could not be resolved"):
        resolve_site_id(
            chat_site_id="   ",
            body_site_id="\t",
            conversation_id=uuid4(),
        )

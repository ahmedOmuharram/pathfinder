"""The staged extract shape: what it holds and what it refuses."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pathfinder.evals.extract import (
    EvalExtract,
    ExtractedStrategy,
    ExtractedTurn,
    ExtractedVerification,
)


def _extract(**overrides: object) -> EvalExtract:
    base: dict[str, object] = {
        "site_id": "plasmodb",
        "assistant_id": "pathfinder",
        "turns": [ExtractedTurn(request="find kinases", reply="built it")],
        "strategy": ExtractedStrategy(
            record_type="transcript",
            step_count=3,
            structure="(A INTERSECT B)",
            strategy_ast={"recordType": "transcript"},
        ),
        "verification": ExtractedVerification(success=True, reason="root size holds"),
    }
    return EvalExtract.model_validate(base | overrides)


def test_an_extract_names_no_user_and_no_thread() -> None:
    fields = set(EvalExtract.model_fields)

    assert "user_id" not in fields
    assert "conversation_id" not in fields


def test_an_extract_refuses_an_email_in_a_request() -> None:
    with pytest.raises(ValidationError, match="email"):
        _extract(turns=[ExtractedTurn(request="mail ada@example.org", reply="ok")])


def test_an_extract_refuses_an_email_in_a_reply() -> None:
    with pytest.raises(ValidationError, match="email"):
        _extract(turns=[ExtractedTurn(request="hi", reply="ask ada@example.org")])


def test_an_extract_refuses_an_email_in_the_verification_reason() -> None:
    with pytest.raises(ValidationError, match="email"):
        _extract(
            verification=ExtractedVerification(
                success=True,
                reason="confirmed by ada@example.org",
            ),
        )


def test_the_content_hash_is_stable_across_two_equal_extracts() -> None:
    assert _extract().content_hash() == _extract().content_hash()


def test_a_different_request_changes_the_content_hash() -> None:
    other = _extract(turns=[ExtractedTurn(request="find proteases", reply="built it")])

    assert _extract().content_hash() != other.content_hash()


def test_the_content_hash_is_a_sha256_digest() -> None:
    digest = _extract().content_hash()

    assert len(digest) == 64
    assert set(digest) <= set("0123456789abcdef")


def test_an_extract_with_no_strategy_is_valid() -> None:
    """A turn that correctly built nothing is exactly the case worth keeping."""
    extract = _extract(strategy=None, verification=None)

    assert extract.strategy is None

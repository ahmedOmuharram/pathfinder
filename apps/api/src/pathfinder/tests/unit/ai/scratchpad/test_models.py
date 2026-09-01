from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from pathfinder.domain.scratchpad.models import (
    CompactionRun,
    Note,
    NoteCreate,
    NoteListResult,
    NoteRef,
    NoteSearchResult,
    NoteUpdate,
)


def _base_note_kwargs() -> dict[str, object]:
    now = datetime.now(UTC)
    return {
        "id": "n-abc123",
        "conversation_id": uuid4(),
        "title": "Candidate search",
        "summary": "GenesByRNASeq with gametocyte_vs_asexual returns 1200.",
        "body": "Details about the search and params.",
        "tags": ["candidate", "search:GenesByRNASeq"],
        "pinned": False,
        "body_tokens": 10,
        "created_at": now,
        "updated_at": now,
    }


class TestNoteValidation:
    def test_roundtrip_basic(self) -> None:
        note = Note(**_base_note_kwargs())
        assert note.title == "Candidate search"
        assert note.tags == ["candidate", "search:genesbyrnaseq"]

    def test_title_too_long_rejected(self) -> None:
        kwargs = _base_note_kwargs()
        kwargs["title"] = "x" * 121
        with pytest.raises(ValidationError):
            Note(**kwargs)

    def test_title_empty_rejected(self) -> None:
        kwargs = _base_note_kwargs()
        kwargs["title"] = ""
        with pytest.raises(ValidationError):
            Note(**kwargs)

    def test_summary_at_cap_accepted(self) -> None:
        # Persistence accepts up to 500 chars even though the model is told
        # to keep summaries ~280 — a slight overflow shouldn't trigger a retry.
        kwargs = _base_note_kwargs()
        kwargs["summary"] = "s" * 500
        note = Note(**kwargs)
        assert len(note.summary) == 500

    def test_summary_too_long_rejected(self) -> None:
        kwargs = _base_note_kwargs()
        kwargs["summary"] = "s" * 501
        with pytest.raises(ValidationError):
            Note(**kwargs)

    def test_body_empty_rejected(self) -> None:
        kwargs = _base_note_kwargs()
        kwargs["body"] = ""
        with pytest.raises(ValidationError):
            Note(**kwargs)

    def test_body_too_long_rejected(self) -> None:
        kwargs = _base_note_kwargs()
        kwargs["body"] = "b" * 20001
        with pytest.raises(ValidationError):
            Note(**kwargs)

    def test_body_tokens_negative_rejected(self) -> None:
        kwargs = _base_note_kwargs()
        kwargs["body_tokens"] = -1
        with pytest.raises(ValidationError):
            Note(**kwargs)


class TestTagNormalization:
    def test_tags_lowercased(self) -> None:
        kwargs = _base_note_kwargs()
        kwargs["tags"] = ["CaNDIdate", "Search:Foo"]
        note = Note(**kwargs)
        assert note.tags == ["candidate", "search:foo"]

    def test_tags_stripped(self) -> None:
        kwargs = _base_note_kwargs()
        kwargs["tags"] = ["  candidate  ", "search:bar "]
        note = Note(**kwargs)
        assert note.tags == ["candidate", "search:bar"]

    def test_tags_deduped_preserving_order(self) -> None:
        kwargs = _base_note_kwargs()
        kwargs["tags"] = ["candidate", "CANDIDATE", "search:foo", "candidate"]
        note = Note(**kwargs)
        assert note.tags == ["candidate", "search:foo"]

    def test_empty_tags_dropped(self) -> None:
        kwargs = _base_note_kwargs()
        kwargs["tags"] = ["candidate", "", "   "]
        note = Note(**kwargs)
        assert note.tags == ["candidate"]

    def test_tag_limit_enforced(self) -> None:
        kwargs = _base_note_kwargs()
        kwargs["tags"] = [f"tag-{i}" for i in range(17)]
        with pytest.raises(ValidationError):
            Note(**kwargs)


class TestNoteCreateValidation:
    def test_minimal_required(self) -> None:
        n = NoteCreate(
            title="t",
            summary="s",
            body="b",
        )
        assert n.tags == []
        assert n.pinned is False

    def test_rejects_oversized_title(self) -> None:
        with pytest.raises(ValidationError):
            NoteCreate(title="x" * 200, summary="s", body="b")


class TestNoteUpdateValidation:
    def test_all_fields_optional(self) -> None:
        u = NoteUpdate()
        assert u.title is None
        assert u.body is None

    def test_partial_update(self) -> None:
        u = NoteUpdate(title="new title")
        assert u.title == "new title"
        assert u.summary is None


class TestNoteRefShape:
    def test_ref_excludes_body(self) -> None:
        now = datetime.now(UTC)
        ref = NoteRef(
            id="n-xyz",
            title="t",
            summary="s",
            tags=["x"],
            pinned=True,
            created_at=now,
        )
        dumped = ref.model_dump(mode="json")
        assert "body" not in dumped


class TestCompactionRun:
    def test_trigger_reason_literal(self) -> None:
        now = datetime.now(UTC)
        r = CompactionRun(
            id=1,
            conversation_id=uuid4(),
            triggered_at=now,
            before_count=55,
            after_count=18,
            before_tokens=12000,
            after_tokens=4200,
            model_id="openai:gpt-4.1-mini",
            cost_usd=Decimal("0.012345"),
            trigger_reason="both",
        )
        assert r.trigger_reason == "both"

    def test_trigger_reason_invalid_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CompactionRun(
                id=1,
                conversation_id=uuid4(),
                triggered_at=datetime.now(UTC),
                before_count=1,
                after_count=1,
                before_tokens=1,
                after_tokens=1,
                model_id="m",
                cost_usd=Decimal(0),
                trigger_reason="sometimes",
            )


def _ref() -> NoteRef:
    return NoteRef(
        id="n-xyz",
        title="t",
        summary="s",
        tags=["x"],
        pinned=False,
        created_at=datetime.now(UTC),
    )


class TestNoteListResult:
    def test_the_envelope_reaches_the_model_in_camel_case(self) -> None:
        """The docstring promises totalNotes, so the wire must carry it."""
        dumped = NoteListResult(
            total_notes=3,
            matches=[_ref()],
            summary="1 of 3 notes.",
        ).model_dump(by_alias=True, mode="json")
        assert dumped["totalNotes"] == 3
        assert "total_notes" not in dumped
        assert dumped["matches"][0]["id"] == "n-xyz"
        assert dumped["summary"] == "1 of 3 notes."

    def test_the_search_envelope_adds_the_query(self) -> None:
        dumped = NoteSearchResult(
            total_notes=1,
            matches=[],
            summary="No notes match 'zqzqzq'.",
            query="zqzqzq",
        ).model_dump(by_alias=True, mode="json")
        assert dumped["query"] == "zqzqzq"
        assert dumped["totalNotes"] == 1
        assert dumped["matches"] == []

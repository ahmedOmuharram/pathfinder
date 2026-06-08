from pathfinder.ai.graph._lead_events import (
    _summarize_sub_agent_call_args,
    _truncate_summary,
)


def test_truncate_short_text_is_unchanged() -> None:
    assert _truncate_summary("short reason", limit=280) == "short reason"


def test_truncate_cuts_at_word_boundary_with_ascii_ellipsis() -> None:
    text = "alpha beta gamma delta epsilon"
    out = _truncate_summary(text, limit=18)
    assert out == "alpha beta..."
    assert out.endswith("...")
    assert "…" not in out
    assert len(out) <= 18


def test_truncate_total_length_within_limit() -> None:
    text = "word " * 100
    out = _truncate_summary(text, limit=280)
    assert len(out) <= 280
    assert out.endswith("...")
    # never splits a word: the char before the ellipsis is not mid-token
    assert not out[:-3].endswith(" ")


def test_truncate_single_long_word_has_no_space() -> None:
    out = _truncate_summary("x" * 500, limit=20)
    assert len(out) <= 20
    assert out.endswith("...")


def test_summarize_started_args_truncates_long_reason_on_word_boundary() -> None:
    reason = "User wants to identify P. falciparum genes " * 20
    out = _summarize_sub_agent_call_args({"reason": reason})
    assert len(out) <= 280
    assert out.endswith("...")
    assert "…" not in out
    assert not out[:-3].endswith(" ")

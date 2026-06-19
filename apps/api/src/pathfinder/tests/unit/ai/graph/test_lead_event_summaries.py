from pathfinder.ai.graph._lead_events import (
    _summarize_delta_dict,
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
    assert "\u2026" not in out
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
    assert "\u2026" not in out
    assert not out[:-3].endswith(" ")


def test_summarize_frame_with_open_questions_is_human_readable() -> None:
    out = _summarize_delta_dict(
        {"frame": {"ready_for_wdk_discovery": False, "blocking_questions": [1, 2, 3]}}
    )
    assert out == "3 open questions"


def test_summarize_frame_single_question_uses_singular() -> None:
    out = _summarize_delta_dict(
        {"frame": {"ready_for_wdk_discovery": False, "blocking_questions": [1]}}
    )
    assert out == "1 open question"


def test_summarize_frame_ready_no_questions() -> None:
    out = _summarize_delta_dict(
        {"frame": {"ready_for_wdk_discovery": True, "blocking_questions": []}}
    )
    assert out == "Ready for discovery"


def test_summarize_frame_not_ready_no_questions() -> None:
    out = _summarize_delta_dict(
        {"frame": {"ready_for_wdk_discovery": False, "blocking_questions": []}}
    )
    assert out == "Problem framed"


def test_summarize_selections_pluralizes_searches() -> None:
    assert (
        _summarize_delta_dict({"selections": {"a": 1, "b": 2}}) == "Selected 2 searches"
    )
    assert _summarize_delta_dict({"selections": {"a": 1}}) == "Selected 1 search"


def test_summarize_plan_steps() -> None:
    assert (
        _summarize_delta_dict({"plan": {"steps": [1, 2]}}) == "Drafted a 2 steps plan"
    )


def test_summarize_outcome_with_failures() -> None:
    out = _summarize_delta_dict(
        {"outcome": {"pushed_step_ids": [1, 2], "failed_steps": [3]}}
    )
    assert out == "Built 2, 1 failed"


def test_summarize_outcome_all_built() -> None:
    out = _summarize_delta_dict(
        {"outcome": {"pushed_step_ids": [1], "failed_steps": []}}
    )
    assert out == "Built 1 step"


def test_summarize_verification_digest() -> None:
    assert (
        _summarize_delta_dict({"digest": {"success": True}}) == "Verified successfully"
    )
    assert _summarize_delta_dict({"digest": {"success": False}}) == "Issues found"

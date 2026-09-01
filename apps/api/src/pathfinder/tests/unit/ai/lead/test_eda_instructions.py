"""The instructions that tell the Lead when EDA is the right route."""

from __future__ import annotations

from pathfinder.ai.lead._lead_instructions import LEAD_INSTRUCTIONS


def test_the_instructions_name_every_eda_tool_in_call_order() -> None:
    order = [
        "search_eda_studies",
        "describe_eda_study",
        "open_eda_analysis",
        "set_eda_filters",
        "preview_eda_subset",
        "run_eda_compute",
        "create_eda_step",
    ]
    positions = [LEAD_INSTRUCTIONS.index(name) for name in order]
    assert positions == sorted(positions)


def test_the_instructions_say_when_eda_beats_a_classic_search() -> None:
    assert "sample-level" in LEAD_INSTRUCTIONS
    assert "eda_analysis_spec" in LEAD_INSTRUCTIONS


def test_the_instructions_forbid_quoting_a_count_before_a_preview() -> None:
    assert "preview_eda_subset" in LEAD_INSTRUCTIONS
    assert "before you state a count" in LEAD_INSTRUCTIONS


def test_the_instructions_say_the_compute_runs_before_the_step() -> None:
    index_compute = LEAD_INSTRUCTIONS.index("run_eda_compute")
    index_step = LEAD_INSTRUCTIONS.index("create_eda_step")
    assert index_compute < index_step
    assert "completes" in LEAD_INSTRUCTIONS


def test_the_eda_section_asks_for_a_caption_on_every_plot() -> None:
    """The figure prints the model's sentence, so the loop must ask for one."""
    eda_section = LEAD_INSTRUCTIONS[
        LEAD_INSTRUCTIONS.index("## EDA: sample-level data") : LEAD_INSTRUCTIONS.index(
            "## User-facing voice"
        )
    ]
    assert "caption" in eda_section


def test_the_instructions_are_ascii_only() -> None:
    assert LEAD_INSTRUCTIONS.isascii()


def test_the_eda_loop_ends_with_verification() -> None:
    """An exported study step is a built step, so the loop closes with VERIFY."""
    eda_section = LEAD_INSTRUCTIONS[
        LEAD_INSTRUCTIONS.index("## EDA: sample-level data") :
    ]
    index_step = eda_section.index("create_eda_step")
    assert "verify_strategy" in eda_section[index_step:]

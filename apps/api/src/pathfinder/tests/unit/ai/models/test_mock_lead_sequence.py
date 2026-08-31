"""The deterministic mock's Lead routing: the FRAME→BUILD→VERIFY build journey
plus the consult / variant / attachment branches. These drive the e2e chat
flows, so a regression here silently reds the whole browser suite."""

from __future__ import annotations

import re

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from pathfinder.ai.models import mock


def _user(text: str) -> ModelRequest:
    return ModelRequest(parts=[UserPromptPart(content=text)])


def _names(seq: list[ToolCallPart]) -> list[str]:
    return [c.tool_name for c in seq]


def test_build_journey_frames_builds_verifies() -> None:
    msgs: list[ModelMessage] = [_user("...3d7...interpro...")]
    assert _names(mock._lead_sequence(msgs)) == [
        "classify_user_intent",
        "frame_problem",
        "build_strategy",
        "verify_strategy",
        "final_result",
    ]


def test_consult_marker_pauses_on_consult_user() -> None:
    msgs: list[ModelMessage] = [_user("Consult me before planning this strategy.")]
    assert _names(mock._lead_sequence(msgs)) == ["consult_user"]


def test_consult_resume_runs_the_build_journey() -> None:
    msgs: list[ModelMessage] = [
        _user("Consult me before planning this strategy."),
        ModelResponse(
            parts=[ToolCallPart(tool_name="consult_user", args={}, tool_call_id="c1")]
        ),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="consult_user", content="answered", tool_call_id="c1"
                ),
                UserPromptPart(content="The user answered your questions: ..."),
            ]
        ),
    ]
    assert _names(mock._lead_sequence(msgs)) == [
        "classify_user_intent",
        "frame_problem",
        "build_strategy",
        "verify_strategy",
        "final_result",
    ]


def test_variant_marker_compares_variants() -> None:
    msgs: list[ModelMessage] = [_user("Compare two search variants for kinases.")]
    assert _names(mock._lead_sequence(msgs)) == [
        "compare_search_variants",
        "final_result",
    ]


def test_plain_prompt_echoes_only() -> None:
    msgs: list[ModelMessage] = [_user("hello there")]
    assert _names(mock._lead_sequence(msgs)) == ["final_result"]


def _prose(seq: list[ToolCallPart]) -> str:
    return str(seq[-1].args_as_dict()["prose"])


# ── The verification-feedback arc ───────────────────────────────────

_BROADEN = "Add InterPro PF00069 (Pkinase) and EC 2.7.-.- to broaden kinases."
_FIX = "Fix the phylogenetic pattern by loosening to %MAMM:N%pfal:Y%."


def test_a_broadening_request_builds_and_reports_the_zero_result() -> None:
    seq = mock._lead_sequence([_user(_BROADEN)])

    assert _names(seq) == [
        "classify_user_intent",
        "frame_problem",
        "build_strategy",
        "verify_strategy",
        "final_result",
    ]
    assert "returned 0" in _prose(seq)
    assert seq[-1].args_as_dict()["nextState"] == "await_user"


def test_the_fix_request_then_verifies_cleanly() -> None:
    seq = mock._lead_sequence([_user(_FIX)])

    assert "Verified end-to-end" in _prose(seq)
    assert seq[-1].args_as_dict()["nextState"] == "complete"


def test_the_feedback_prose_states_the_failure_and_not_the_success() -> None:
    # The specs read these two apart by their text, so they must not overlap.
    feedback = _prose(mock._lead_sequence([_user(_BROADEN)]))
    success = _prose(mock._lead_sequence([_user(_FIX)]))

    assert not re.search(r"verified end-to-end|root size", feedback, re.IGNORECASE)
    assert not re.search(r"returned 0|too narrow|loosen", success, re.IGNORECASE)


def test_the_digest_agrees_with_the_lead_about_failure() -> None:
    # A digest that reports success over a failed build is the contradiction
    # the ledger cannot show the user.
    assert mock.verification_succeeds(_FIX) is True
    assert mock.verification_succeeds(_BROADEN) is False


# ── Site-aware canned specs ─────────────────────────────────────────


def test_the_canned_spec_takes_the_organism_of_the_site_it_runs_on() -> None:
    spec = mock.spec_for("create step", "cryptodb")

    assert spec.criteria[0].values["organism"] == ["Cryptosporidium parvum Iowa II"]


def test_a_broadening_request_frames_two_leaves() -> None:
    spec = mock.spec_for(_BROADEN, "plasmodb")

    assert [c.search_name for c in spec.criteria] == ["GenesByText", "GenesByTaxon"]


def test_a_go_request_frames_the_go_search() -> None:
    spec = mock.spec_for("build a GO term strategy for kinases", "plasmodb")

    assert [c.search_name for c in spec.criteria] == ["GenesByGoTerm"]


def test_an_all_parameter_request_frames_three_search_types() -> None:
    spec = mock.spec_for("Build a comprehensive kinase strategy", "plasmodb")

    assert [c.search_name for c in spec.criteria] == [
        "GenesByText",
        "GenesByGoTerm",
        "GenesByTaxon",
    ]


def test_an_impact_question_does_not_rebuild() -> None:
    # It names InterPro, which otherwise routes to a build.
    seq = mock._lead_sequence(
        [_user("What's the impact of switching the InterPro/GO combine to INTERSECT?")]
    )

    assert _names(seq) == ["final_result"]


def test_an_edit_marker_routes_to_the_edit_dispatch() -> None:
    msgs: list[ModelMessage] = [
        _user("Swap the organism on the taxon criterion and keep the rest.")
    ]
    assert _names(mock._lead_sequence(msgs)) == [
        "classify_user_intent",
        "edit_strategy",
        "final_result",
    ]


def test_a_remember_request_stores_the_preference_and_builds_nothing() -> None:
    msgs: list[ModelMessage] = [
        _user("Please remember for future sessions: I work with P. falciparum 3D7.")
    ]

    assert _names(mock._lead_sequence(msgs)) == [
        "classify_user_intent",
        "remember",
        "final_result",
    ]


def test_a_context_statement_answers_in_prose_and_builds_nothing() -> None:
    msgs: list[ModelMessage] = [
        _user("I'm investigating virulence factors in Leishmania major")
    ]

    assert _names(mock._lead_sequence(msgs)) == [
        "classify_user_intent",
        "final_result",
    ]


def test_the_classification_is_made_once_per_turn() -> None:
    """A second turn re-classifies; the run's first classification is not reused."""
    first_turn = [
        _user("...3d7...interpro..."),
        ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="classify_user_intent", args={}, tool_call_id="c0"
                )
            ]
        ),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="classify_user_intent",
                    content="ok",
                    tool_call_id="c0",
                )
            ]
        ),
    ]
    second_turn: list[ModelMessage] = [
        *first_turn,
        _user("Swap the organism on the taxon criterion and keep the rest."),
    ]

    assert mock._lead_script(second_turn).tool_name == "classify_user_intent"

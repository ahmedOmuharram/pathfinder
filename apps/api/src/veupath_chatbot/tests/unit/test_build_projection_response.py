"""Tests for build_projection_response message validation resilience."""

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

from veupath_chatbot.transport.http.routers.strategies._shared import (
    build_projection_response,
    derive_steps_from_plan,
)


def _make_projection(**overrides):
    """Create a minimal mock StreamProjection."""
    stream = MagicMock()
    stream.created_at = datetime.now(UTC)
    stream.site_id = overrides.get("site_id", "plasmodb")

    proj = MagicMock()
    proj.stream_id = overrides.get("stream_id", uuid4())
    proj.name = overrides.get("name", "Test Strategy")
    proj.record_type = overrides.get("record_type")
    proj.wdk_strategy_id = overrides.get("wdk_strategy_id")
    proj.is_saved = overrides.get("is_saved", False)
    proj.model_id = overrides.get("model_id")
    proj.message_count = overrides.get("message_count", 0)
    proj.step_count = overrides.get("step_count", 0)
    proj.plan = overrides.get("plan", {})
    proj.steps = overrides.get("steps", [])
    proj.root_step_id = overrides.get("root_step_id")
    proj.estimated_size = overrides.get("estimated_size")
    proj.updated_at = overrides.get("updated_at", datetime.now(UTC))
    proj.gene_set_id = overrides.get("gene_set_id")
    proj.dismissed_at = overrides.get("dismissed_at")
    proj.stream = stream
    proj.site_id = stream.site_id
    return proj


def _make_msg(role: str, content: str, **extra) -> dict:
    return {
        "role": role,
        "content": content,
        "timestamp": datetime.now(UTC).isoformat(),
        **extra,
    }


class TestBuildProjectionResponseMessages:
    def test_returns_messages_when_all_valid(self):
        proj = _make_projection()
        messages = [
            _make_msg("user", "hello"),
            _make_msg("assistant", "hi there"),
        ]
        resp = build_projection_response(proj, messages=messages)
        assert resp.messages is not None
        assert len(resp.messages) == 2
        assert resp.messages[0].role == "user"
        assert resp.messages[1].role == "assistant"

    def test_returns_none_when_no_messages(self):
        proj = _make_projection()
        resp = build_projection_response(proj)
        assert resp.messages is None

    def test_returns_none_when_messages_is_empty_list(self):
        proj = _make_projection()
        resp = build_projection_response(proj, messages=[])
        assert resp.messages is None

    def test_skips_malformed_message_keeps_valid_ones(self):
        """A single bad message should NOT drop all other valid messages."""
        proj = _make_projection()
        messages = [
            _make_msg("user", "hello"),
            {"role": "assistant"},  # missing required 'content' and 'timestamp'
            _make_msg("assistant", "I'm still here"),
        ]
        resp = build_projection_response(proj, messages=messages)
        assert resp.messages is not None
        assert len(resp.messages) == 2
        assert resp.messages[0].content == "hello"
        assert resp.messages[1].content == "I'm still here"

    def test_skips_non_dict_entries(self):
        proj = _make_projection()
        messages: list = [
            _make_msg("user", "hello"),
            "not a dict",
            42,
            _make_msg("assistant", "response"),
        ]
        resp = build_projection_response(proj, messages=messages)
        assert resp.messages is not None
        assert len(resp.messages) == 2

    def test_preserves_tool_calls(self):
        proj = _make_projection()
        messages = [
            _make_msg(
                "assistant",
                "Let me search for that",
                toolCalls=[{"id": "t1", "name": "search", "arguments": {"q": "gene"}}],
            ),
        ]
        resp = build_projection_response(proj, messages=messages)
        assert resp.messages is not None
        assert len(resp.messages) == 1
        assert resp.messages[0].tool_calls is not None
        assert resp.messages[0].tool_calls[0].name == "search"

    def test_all_messages_malformed_returns_none(self):
        proj = _make_projection()
        messages = [
            {"role": "user"},  # missing content and timestamp
            {"content": "no role"},  # missing role and timestamp
        ]
        resp = build_projection_response(proj, messages=messages)
        # All messages failed validation → msg_responses is empty → None
        assert resp.messages is None


# -- Plan for a single search step (reused across tests) --
_SINGLE_STEP_PLAN = {
    "recordType": "GeneRecordClasses.GeneRecordClass",
    "root": {
        "id": "step_1",
        "searchName": "GenesByTaxon",
        "parameters": {"organism": "Plasmodium falciparum 3D7"},
    },
}

_TWO_STEP_PLAN = {
    "recordType": "GeneRecordClasses.GeneRecordClass",
    "root": {
        "id": "step_2",
        "searchName": "boolean_question",
        "operator": "INTERSECT",
        "primaryInput": {
            "id": "step_1",
            "searchName": "GenesByTaxon",
            "parameters": {"organism": "Plasmodium falciparum 3D7"},
        },
        "secondaryInput": {
            "id": "step_3",
            "searchName": "GenesByGoTerm",
            "parameters": {"GoTerm": "GO:0006096"},
        },
    },
}


class TestDeriveStepsFromPlan:
    """Tests for derive_steps_from_plan (read-time derivation)."""

    def test_empty_plan_returns_empty(self):
        assert derive_steps_from_plan({}) == []

    def test_none_plan_returns_empty(self):
        assert derive_steps_from_plan(None) == []  # type: ignore[arg-type]

    def test_invalid_plan_returns_empty(self):
        assert derive_steps_from_plan({"root": "not_a_dict"}) == []

    def test_single_step_plan_returns_one_step(self):
        steps = derive_steps_from_plan(_SINGLE_STEP_PLAN)
        assert len(steps) == 1
        assert steps[0].id == "step_1"
        assert steps[0].search_name == "GenesByTaxon"
        assert steps[0].kind == "search"

    def test_two_step_plan_returns_three_steps(self):
        steps = derive_steps_from_plan(_TWO_STEP_PLAN)
        assert len(steps) == 3
        ids = {s.id for s in steps}
        assert ids == {"step_1", "step_2", "step_3"}

    def test_derived_steps_have_record_type(self):
        steps = derive_steps_from_plan(_SINGLE_STEP_PLAN)
        assert steps[0].record_type == "GeneRecordClasses.GeneRecordClass"


class TestBuildProjectionResponseDerivedSteps:
    """Tests that build_projection_response derives steps from plan (not projection.steps)."""

    def test_steps_derived_from_plan_not_stored(self):
        """Even if projection.steps is empty, steps come from plan."""
        proj = _make_projection(plan=_SINGLE_STEP_PLAN, steps=[])
        resp = build_projection_response(proj)
        assert len(resp.steps) == 1
        assert resp.steps[0].id == "step_1"

    def test_root_step_id_derived_from_plan(self):
        proj = _make_projection(plan=_SINGLE_STEP_PLAN, root_step_id=None)
        resp = build_projection_response(proj)
        assert resp.root_step_id == "step_1"

    def test_empty_plan_gives_empty_steps(self):
        proj = _make_projection(plan={})
        resp = build_projection_response(proj)
        assert resp.steps == []
        assert resp.root_step_id is None

"""Tests for projection handlers — steps column consistency."""

from pathfinder.domain.strategy.ast import PlanStepNode
from pathfinder.domain.strategy.conversation_state import ConversationState
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.plan_payload import StrategyPlanPayload
from pathfinder.platform.projection import (
    _build_conversation_state_update,
    _project_graph_cleared,
    _project_graph_plan,
    _project_graph_snapshot,
)
from pathfinder.platform.types import JSONObject


def _leaf(step_id: str = "step_leaf01") -> PlanStepNode:
    return PlanStepNode(
        search_name="GenesByTaxon",
        display_name="Taxon",
        parameters={"organism": "Plasmodium falciparum 3D7"},
        id=step_id,
    )


def _plan_payload(root: PlanStepNode) -> StrategyPlanPayload:
    return StrategyPlanPayload(record_type="transcript", root=root)


class TestProjectGraphPlan:
    def test_writes_both_step_count_and_steps(self) -> None:
        leaf = _leaf()
        payload = _plan_payload(leaf)
        data: JSONObject = {
            "plan": payload.model_dump(by_alias=True, mode="json"),
        }

        updates: dict[str, object] = {}
        _project_graph_plan(updates, data)

        assert updates["step_count"] == 1
        assert isinstance(updates["steps"], list)
        steps = updates["steps"]
        assert len(steps) == 1
        assert steps[0]["id"] == "step_leaf01"
        assert steps[0]["searchName"] == "GenesByTaxon"
        assert steps[0]["kind"] == "search"

    def test_combine_writes_correct_step_count_and_steps(self) -> None:
        left = _leaf("step_left01")
        right = PlanStepNode(
            search_name="GenesByLocation",
            display_name="Location",
            parameters={},
            id="step_right1",
        )
        combine = PlanStepNode(
            search_name="__combine__",
            primary_input=left,
            secondary_input=right,
            operator=CombineOp.INTERSECT,
            parameters={},
            id="step_comb01",
        )
        payload = _plan_payload(combine)
        data: JSONObject = {
            "plan": payload.model_dump(by_alias=True, mode="json"),
        }

        updates: dict[str, object] = {}
        _project_graph_plan(updates, data)

        assert updates["step_count"] == 3
        steps = updates["steps"]
        assert len(steps) == 3
        assert steps[2]["operator"] == "INTERSECT"


class TestProjectGraphSnapshot:
    def test_writes_steps_from_snapshot(self) -> None:
        snapshot_steps: list[JSONObject] = [
            {"id": "s1", "searchName": "GenesByTaxon"},
            {"id": "s2", "searchName": "GenesByLocation"},
        ]
        data: JSONObject = {
            "graphSnapshot": {
                "steps": snapshot_steps,
                "rootStepId": "s2",
            },
        }

        updates: dict[str, object] = {}
        _project_graph_snapshot(updates, data)

        assert updates["step_count"] == 2
        assert updates["steps"] == snapshot_steps

    def test_no_steps_when_snapshot_empty(self) -> None:
        data: JSONObject = {
            "graphSnapshot": {
                "steps": [],
            },
        }

        updates: dict[str, object] = {}
        _project_graph_snapshot(updates, data)

        assert "steps" not in updates
        assert "step_count" not in updates


class TestProjectGraphCleared:
    def test_resets_both_step_count_and_steps(self) -> None:
        updates: dict[str, object] = {}
        _project_graph_cleared(updates)

        assert updates["step_count"] == 0
        assert updates["steps"] == []

    def test_resets_conversation_state(self) -> None:
        updates: dict[str, object] = {}
        _project_graph_cleared(updates)

        assert updates["conversation_state"] == {}


class TestProjectConversationState:
    def test_phase_change_started_updates_state(self) -> None:
        existing = ConversationState()
        result = _build_conversation_state_update(
            existing,
            "phase_change",
            {"phase": "scoping", "status": "started", "messageId": "msg-1"},
        )
        assert result is not None
        assert result.current_phase == "scoping"
        assert result.phase_status == "started"

    def test_phase_change_completed_tracks_in_phases_completed(self) -> None:
        existing = ConversationState(
            current_phase="scoping", phase_status="started"
        )
        result = _build_conversation_state_update(
            existing,
            "phase_change",
            {"phase": "scoping", "status": "completed"},
        )
        assert result is not None
        assert "scoping" in result.phases_completed

    def test_plan_presented_updates_plan_fields(self) -> None:
        existing = ConversationState(current_phase="planning")
        result = _build_conversation_state_update(
            existing,
            "plan_presented",
            {"plan": {"id": "plan_abc123", "title": "Test"}},
        )
        assert result is not None
        assert result.plan_id == "plan_abc123"
        assert result.plan_status == "presented"

    def test_plan_approved_updates_plan_status(self) -> None:
        existing = ConversationState(
            plan_id="plan_abc123", plan_status="presented"
        )
        result = _build_conversation_state_update(
            existing,
            "plan_approved",
            {"planId": "plan_abc123", "plan": {}},
        )
        assert result is not None
        assert result.plan_status == "approved"

    def test_message_end_returns_existing(self) -> None:
        existing = ConversationState(
            current_phase="execution", phase_status="started"
        )
        result = _build_conversation_state_update(existing, "message_end", {})
        assert result is not None
        assert result.current_phase == "execution"

    def test_irrelevant_event_returns_none(self) -> None:
        existing = ConversationState()
        result = _build_conversation_state_update(
            existing, "assistant_delta", {}
        )
        assert result is None

"""Tests for plan_ast helpers — derive_plan_steps_json."""

from pathfinder.domain.strategy.ast import PlanStepNode
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.plan_ast import derive_plan_steps_json
from pathfinder.domain.strategy.plan_payload import StrategyPlanPayload


def _leaf(search_name: str = "GenesByTaxon", display_name: str | None = "Taxon") -> PlanStepNode:
    return PlanStepNode(
        search_name=search_name,
        display_name=display_name,
        parameters={"organism": "Plasmodium falciparum 3D7"},
        id="step_leaf01",
    )


def _payload(root: PlanStepNode) -> StrategyPlanPayload:
    return StrategyPlanPayload(record_type="transcript", root=root)


class TestDerivePlanStepsJson:
    def test_single_leaf(self) -> None:
        payload = _payload(_leaf())
        result = derive_plan_steps_json(payload)

        assert len(result) == 1
        step = result[0]
        assert step["id"] == "step_leaf01"
        assert step["searchName"] == "GenesByTaxon"
        assert step["displayName"] == "Taxon"
        assert step["kind"] == "search"
        assert step["operator"] is None

    def test_combine_node(self) -> None:
        left = PlanStepNode(
            search_name="GenesByTaxon",
            display_name="Taxon",
            parameters={},
            id="step_left01",
        )
        right = PlanStepNode(
            search_name="GenesByLocation",
            display_name="Location",
            parameters={},
            id="step_right1",
        )
        combine = PlanStepNode(
            search_name="__combine__",
            display_name=None,
            primary_input=left,
            secondary_input=right,
            operator=CombineOp.INTERSECT,
            parameters={},
            id="step_comb01",
        )
        payload = _payload(combine)
        result = derive_plan_steps_json(payload)

        # walk_step_tree visits primary, secondary, then current
        assert len(result) == 3
        assert result[0]["id"] == "step_left01"
        assert result[0]["kind"] == "search"
        assert result[1]["id"] == "step_right1"
        assert result[1]["kind"] == "search"
        assert result[2]["id"] == "step_comb01"
        assert result[2]["kind"] == "combine"
        assert result[2]["operator"] == "INTERSECT"

    def test_transform_node(self) -> None:
        leaf = _leaf()
        transform = PlanStepNode(
            search_name="GenesByOrthologPattern",
            display_name="Ortholog",
            primary_input=leaf,
            parameters={},
            id="step_xfrm01",
        )
        payload = _payload(transform)
        result = derive_plan_steps_json(payload)

        assert len(result) == 2
        assert result[0]["id"] == "step_leaf01"
        assert result[0]["kind"] == "search"
        assert result[1]["id"] == "step_xfrm01"
        assert result[1]["kind"] == "transform"
        assert result[1]["operator"] is None

    def test_null_display_name(self) -> None:
        leaf = PlanStepNode(
            search_name="GenesByTaxon",
            display_name=None,
            parameters={},
            id="step_noname1",
        )
        payload = _payload(leaf)
        result = derive_plan_steps_json(payload)

        assert result[0]["displayName"] is None

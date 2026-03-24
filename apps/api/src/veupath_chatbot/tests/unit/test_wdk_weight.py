"""Tests for wdk_weight field on PlanStepNode."""

from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.services.strategies.schemas import StrategyPlanPayload


class TestWdkWeightRoundTrip:
    """Tests for wdk_weight round-trip: model_dump -> model_validate."""

    def test_round_trip_with_weight(self) -> None:
        node = PlanStepNode(search_name="GenesByTaxon", wdk_weight=10)
        serialized = {
            "recordType": "gene",
            "root": node.model_dump(by_alias=True, exclude_none=True, mode="json"),
        }
        ast = StrategyPlanPayload.model_validate(serialized)
        assert ast.root.wdk_weight == 10

    def test_round_trip_without_weight(self) -> None:
        node = PlanStepNode(search_name="GenesByTaxon")
        serialized = {
            "recordType": "gene",
            "root": node.model_dump(by_alias=True, exclude_none=True, mode="json"),
        }
        ast = StrategyPlanPayload.model_validate(serialized)
        assert ast.root.wdk_weight is None

    def test_round_trip_preserves_zero_weight(self) -> None:
        node = PlanStepNode(search_name="GenesByTaxon", wdk_weight=0)
        serialized = {
            "recordType": "gene",
            "root": node.model_dump(by_alias=True, exclude_none=True, mode="json"),
        }
        ast = StrategyPlanPayload.model_validate(serialized)
        assert ast.root.wdk_weight == 0

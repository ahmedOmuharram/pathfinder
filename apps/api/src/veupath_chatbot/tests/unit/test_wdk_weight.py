"""Tests for wdk_weight field on PlanStepNode."""

from veupath_chatbot.domain.strategy.ast import PlanStepNode, StrategyAST


class TestWdkWeightToDict:
    """Tests for wdk_weight serialization in to_dict()."""

    def test_to_dict_includes_wdk_weight_when_set(self) -> None:
        node = PlanStepNode(search_name="GenesByTaxon", wdk_weight=5)
        result = node.to_dict()
        assert result["wdkWeight"] == 5

    def test_to_dict_omits_wdk_weight_when_none(self) -> None:
        node = PlanStepNode(search_name="GenesByTaxon", wdk_weight=None)
        result = node.to_dict()
        assert "wdkWeight" not in result

    def test_to_dict_omits_wdk_weight_by_default(self) -> None:
        node = PlanStepNode(search_name="GenesByTaxon")
        result = node.to_dict()
        assert "wdkWeight" not in result

    def test_to_dict_wdk_weight_zero(self) -> None:
        """Zero is a valid weight and should be included."""
        node = PlanStepNode(search_name="GenesByTaxon", wdk_weight=0)
        result = node.to_dict()
        assert result["wdkWeight"] == 0


class TestWdkWeightModelValidate:
    """Tests for wdk_weight deserialization in model_validate()."""

    def test_model_validate_parses_wdk_weight(self) -> None:
        data = {
            "recordType": "gene",
            "root": {
                "searchName": "GenesByTaxon",
                "parameters": {},
                "wdkWeight": 5,
            },
        }
        ast = StrategyAST.model_validate(data)
        assert ast.root.wdk_weight == 5

    def test_model_validate_wdk_weight_absent(self) -> None:
        data = {
            "recordType": "gene",
            "root": {
                "searchName": "GenesByTaxon",
                "parameters": {},
            },
        }
        ast = StrategyAST.model_validate(data)
        assert ast.root.wdk_weight is None

    def test_model_validate_wdk_weight_zero(self) -> None:
        data = {
            "recordType": "gene",
            "root": {
                "searchName": "GenesByTaxon",
                "parameters": {},
                "wdkWeight": 0,
            },
        }
        ast = StrategyAST.model_validate(data)
        assert ast.root.wdk_weight == 0


class TestWdkWeightRoundTrip:
    """Tests for wdk_weight round-trip: to_dict -> model_validate."""

    def test_round_trip_with_weight(self) -> None:
        node = PlanStepNode(search_name="GenesByTaxon", wdk_weight=10)
        serialized = {
            "recordType": "gene",
            "root": node.to_dict(),
        }
        ast = StrategyAST.model_validate(serialized)
        assert ast.root.wdk_weight == 10

    def test_round_trip_without_weight(self) -> None:
        node = PlanStepNode(search_name="GenesByTaxon")
        serialized = {
            "recordType": "gene",
            "root": node.to_dict(),
        }
        ast = StrategyAST.model_validate(serialized)
        assert ast.root.wdk_weight is None

    def test_round_trip_preserves_zero_weight(self) -> None:
        node = PlanStepNode(search_name="GenesByTaxon", wdk_weight=0)
        serialized = {
            "recordType": "gene",
            "root": node.to_dict(),
        }
        ast = StrategyAST.model_validate(serialized)
        assert ast.root.wdk_weight == 0

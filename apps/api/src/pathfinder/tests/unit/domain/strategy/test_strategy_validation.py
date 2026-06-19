from __future__ import annotations

from pathfinder.domain.parameters.values import StringValue
from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.domain.strategy.validate import StrategyValidator, validate_strategy


def _leaf(search_name: str = "GenesByText") -> StrategyStepNode:
    return StrategyStepNode(
        id="leaf",
        search_name=search_name,
        parameters={"text_expression": StringValue(value="kinase")},
    )


def test_valid_leaf_passes() -> None:
    result = validate_strategy(_leaf(), "transcript")
    assert result.valid
    assert result.errors == []


def test_empty_search_name_is_missing_search_name() -> None:
    result = validate_strategy(_leaf(search_name=""), "transcript")
    assert not result.valid
    codes = [e.code for e in result.errors]
    assert "MISSING_SEARCH_NAME" in codes
    issue = next(e for e in result.errors if e.code == "MISSING_SEARCH_NAME")
    assert issue.path == "root.searchName"


def test_empty_record_type_is_missing_record_type() -> None:
    result = validate_strategy(_leaf(), "")
    assert not result.valid
    issue = next(e for e in result.errors if e.code == "MISSING_RECORD_TYPE")
    assert issue.path == "recordType"


def test_unknown_search_when_catalog_provided() -> None:
    validator = StrategyValidator(
        available_searches={"transcript": ["GenesByText", "GenesByGoTerm"]},
    )
    result = validator.validate(_leaf(search_name="NotARealSearch"), "transcript")
    assert not result.valid
    issue = next(e for e in result.errors if e.code == "UNKNOWN_SEARCH")
    assert issue.message == "Unknown search: NotARealSearch"
    assert issue.path == "root.searchName"


def test_known_search_in_catalog_passes() -> None:
    validator = StrategyValidator(
        available_searches={"transcript": ["GenesByText"]},
    )
    result = validator.validate(_leaf(search_name="GenesByText"), "transcript")
    assert result.valid


def test_search_valid_for_other_record_type_is_unknown_here() -> None:
    validator = StrategyValidator(
        available_searches={"gene": ["GenesByText"], "transcript": ["GenesByGoTerm"]},
    )
    result = validator.validate(_leaf(search_name="GenesByText"), "transcript")
    assert not result.valid
    assert any(e.code == "UNKNOWN_SEARCH" for e in result.errors)

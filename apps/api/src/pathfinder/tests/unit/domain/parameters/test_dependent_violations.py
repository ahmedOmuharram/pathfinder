from __future__ import annotations

from pathfinder.domain.parameters.specs import (
    ParamSpecNormalized,
    find_dependent_value_violations,
)
from pathfinder.domain.parameters.wdk_vocab import WDKVocabTerm


def _vocab(*terms: str) -> list[WDKVocabTerm]:
    return [WDKVocabTerm(root=(t, t, None)) for t in terms]


def _specs(child_vocab: list[WDKVocabTerm]) -> dict[str, ParamSpecNormalized]:
    parent = ParamSpecNormalized(
        name="document_type",
        param_type="string",
        dependent_params=("text_fields",),
    )
    child = ParamSpecNormalized(
        name="text_fields",
        param_type="multi-pick-vocabulary",
        vocabulary=child_vocab,
    )
    return {"document_type": parent, "text_fields": child}


def test_stale_dependent_value_after_refresh_is_flagged() -> None:
    specs = _specs(_vocab("product", "name"))
    assert find_dependent_value_violations(specs, {"text_fields": ["was_valid"]}) == [
        ("text_fields", ["was_valid"])
    ]


def test_value_in_refreshed_vocab_is_not_flagged() -> None:
    specs = _specs(_vocab("product", "name"))
    assert find_dependent_value_violations(specs, {"text_fields": ["product"]}) == []


def test_partial_stale_reports_only_the_bad_values() -> None:
    specs = _specs(_vocab("product", "name"))
    assert find_dependent_value_violations(
        specs, {"text_fields": ["product", "gone"]}
    ) == [("text_fields", ["gone"])]


def test_empty_dependent_value_is_skipped() -> None:
    specs = _specs(_vocab("product"))
    assert find_dependent_value_violations(specs, {"text_fields": []}) == []


def test_non_dependent_param_is_not_checked() -> None:
    solo = ParamSpecNormalized(
        name="solo", param_type="string", vocabulary=_vocab("only")
    )
    assert find_dependent_value_violations({"solo": solo}, {"solo": "anything"}) == []

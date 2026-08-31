"""GenesByText's ``document_type`` is hidden (isVisible=False), required
(allowEmptyValue=False), and fixed to ``initialDisplayValue='gene'``. The model
can't see it (it's excluded from the offered param list), so it omits it — yet
the required-check flags it missing, AND if the model adds it the unknown-key
check rejects it ("does not exist"). That contradiction spirals create_plan.

Hidden required params are plumbing: fill them from their fixed default so they
reach WDK and aren't reported missing. Visible required params stay the model's
job and must NOT be auto-filled (filling them masks genuinely-missing input).
"""

from __future__ import annotations

from pathfinder.domain.parameters.specs import (
    ParamSpecNormalized,
    fill_hidden_required_defaults,
    find_missing_required_params,
)
from pathfinder.domain.parameters.value_codec import to_decoded_map
from pathfinder.domain.parameters.values import StringValue


def _genes_by_text_specs() -> dict[str, ParamSpecNormalized]:
    return {
        "text_expression": ParamSpecNormalized(
            name="text_expression",
            param_type="string",
            allow_empty_value=False,
            is_visible=True,
            initial_display_value="*reductase",
        ),
        "document_type": ParamSpecNormalized(
            name="document_type",
            param_type="string",
            allow_empty_value=False,
            is_visible=False,
            initial_display_value="gene",
        ),
    }


def test_hidden_required_param_is_filled_from_its_fixed_default() -> None:
    specs = _genes_by_text_specs()
    # The model supplied only the visible param it can see.
    params = {"text_expression": StringValue(value="kinase")}
    filled = fill_hidden_required_defaults(specs, params)
    assert filled["document_type"] == StringValue(value="gene")
    # The model's own value is left untouched.
    assert filled["text_expression"] == StringValue(value="kinase")


def test_visible_required_param_is_not_auto_filled() -> None:
    specs = _genes_by_text_specs()
    # text_expression omitted — a genuinely-missing VISIBLE required param.
    # It must NOT be silently filled with the form-example default.
    filled = fill_hidden_required_defaults(specs, {})
    assert "text_expression" not in filled
    assert filled["document_type"] == StringValue(value="gene")


def test_filling_resolves_the_missing_required_contradiction() -> None:
    specs = _genes_by_text_specs()
    params = {"text_expression": StringValue(value="kinase")}
    filled = fill_hidden_required_defaults(specs, params)
    # After filling plumbing, only genuinely-missing visible params remain.
    assert find_missing_required_params(specs, to_decoded_map(filled)) == []


def test_genuinely_missing_visible_param_still_reported() -> None:
    specs = _genes_by_text_specs()
    filled = fill_hidden_required_defaults(specs, {})
    assert find_missing_required_params(specs, to_decoded_map(filled)) == [
        "text_expression"
    ]

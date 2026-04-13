"""Regression tests for Issue 1: Planning renders free text instead of structured widgets.

The bug: ``_build_param`` in ``_plan_models.py`` has a fallback at lines 169-176
that hardcodes ``param_type="string"`` when no WDK spec is available.  When a
spec IS available (lines 156-168), it correctly uses the WDK metadata.  But
silently dropping to "string" hides rich widget information from the frontend,
so planning questions render as plain text inputs instead of structured
WDK widgets (TreeBox, TypeAhead, Select, Checkbox).

These tests document the CORRECT behavior:

1. When a spec IS available, every relevant WDK field (``param_type``,
   ``constraints``, ``options``, ``description``, ``depends_on``, ``required``)
   MUST flow through ``_build_param`` into the ``PlannedParameter``.
2. When no spec is available, we should FAIL FAST (``ValueError``) instead of
   silently synthesising a "string" fallback.  Data-shape corruption has no
   business being swept under the rug — the frontend cannot render a real
   widget from a type it has never heard of.

Matching the patterns used in ``test_plan_tools.py``.
"""

from __future__ import annotations

import pytest

from pathfinder.ai.tools.standalone._plan_models import (
    PlannedStepInput,
    _build_param,
    _convert_step,
)
from pathfinder.domain.parameters.specs import ParamSpecNormalized
from pathfinder.domain.strategy.plan import ParamStatus, StepType

# ---------------------------------------------------------------------------
# _build_param — unit tests for a single parameter
# ---------------------------------------------------------------------------


def test_build_param_preserves_wdk_param_type_treebox() -> None:
    """_build_param MUST use spec.param_type verbatim, not coerce to 'string'.

    A TreeBox-enum parameter in WDK has ``param_type="treebox-enum-param"``
    and ``display_type="treeBox"``. The frontend widget registry in
    ``apps/web/src/features/strategy/editor/widgets/registry.ts`` dispatches
    on displayType, and the paramType is used for validation/coercion. If we
    overwrite it with "string", the frontend sees a mismatched shape and
    falls back to a plain text input.
    """
    spec = ParamSpecNormalized(
        name="organism",
        param_type="treebox-enum-param",
        display_type="treeBox",
        vocabulary=[
            {"value": "pfal", "label": "P. falciparum"},
            {"value": "pvivax", "label": "P. vivax"},
        ],
        help="Select one or more organisms",
        allow_empty_value=False,
        dependent_params=("geneBooleanFilter",),
    )

    planned = _build_param("organism", '["pfal"]', spec)

    # The WDK param_type must survive end-to-end.
    assert planned.param_type == "treebox-enum-param"
    # Required because allow_empty_value is False.
    assert planned.required is True
    # Description copied from spec.help.
    assert planned.description == "Select one or more organisms"
    # dependent_params becomes depends_on.
    assert planned.depends_on == ["geneBooleanFilter"]
    # Status reflects the value presence.
    assert planned.status == ParamStatus.SET


def test_build_param_preserves_constraints_for_numeric() -> None:
    """Numeric parameters must surface ``isNumber``, ``minValue``, ``maxValue``.

    The frontend's ``StringParam`` widget reads ``spec.isNumber`` and
    ``spec.min``/``spec.max`` to decide whether to render an ``<input
    type="number">`` with a ``min``/``max`` clamp.  If these constraints are
    dropped, the frontend renders a generic text box with no validation.
    """
    spec = ParamSpecNormalized(
        name="expression_threshold",
        param_type="number",
        display_type="",
        is_number=True,
        min_value=0.0,
        max_value=100.0,
        increment=0.5,
    )

    planned = _build_param("expression_threshold", "42", spec)

    assert planned.param_type == "number"
    assert planned.constraints is not None
    # Exact WDK field names.
    assert planned.constraints["isNumber"] is True
    assert planned.constraints["minValue"] == 0.0
    assert planned.constraints["maxValue"] == 100.0
    assert planned.constraints["increment"] == 0.5
    # displayType is empty string → skipped by _build_constraints.
    assert "displayType" not in planned.constraints


def test_build_param_preserves_vocabulary_options() -> None:
    """A vocabulary list MUST flow through to ``options`` as value strings.

    The frontend's TreeBox/Select/Checkbox widgets rely on this list to
    render the user's choices.  Dropping it means the widget has nothing
    to display.
    """
    spec = ParamSpecNormalized(
        name="species",
        param_type="single-pick-vocabulary",
        display_type="select",
        vocabulary=[
            {"value": "opt-a", "label": "Option A"},
            {"value": "opt-b", "label": "Option B"},
        ],
    )

    planned = _build_param("species", "opt-a", spec)

    assert planned.options == ["opt-a", "opt-b"]
    assert planned.param_type == "single-pick-vocabulary"
    assert planned.constraints is not None
    assert planned.constraints["displayType"] == "select"


def test_build_param_raises_when_no_spec_available() -> None:
    """Post-fix: ``_build_param`` must FAIL FAST when no WDK spec is supplied.

    The current buggy fallback silently returns ``param_type="string"`` —
    that's data corruption masquerading as graceful degradation.  The
    frontend then tries to render a "string" param for something that is
    actually a TreeBox, TypeAhead, or Number, producing a broken UX.

    The correct behavior is to refuse to construct a PlannedParameter
    without a spec.  Callers (``_convert_step``, ``_apply_step_patches``)
    must always supply one — if discovery has not run yet, they should
    surface that as a discovery error instead of pretending the param is
    a free-text string.

    This test documents the post-fix contract.  It CURRENTLY FAILS because
    ``_build_param(name, value, None)`` returns a PlannedParameter with
    ``param_type="string"`` instead of raising.
    """
    with pytest.raises(ValueError, match=r"spec|wdk|discover|param"):
        _build_param("organism", '["pfal"]', None)


# ---------------------------------------------------------------------------
# _convert_step — integration test across the full step conversion
# ---------------------------------------------------------------------------


def test_convert_step_with_param_specs_enriches_all_params() -> None:
    """All parameters in the step MUST be enriched from their corresponding spec.

    This exercises the full path ``_convert_step → _build_param`` for every
    parameter on the step — mirroring what the LLM delivers when it calls
    ``create_plan`` and the server merges in discovery results.
    """
    step_input = PlannedStepInput(
        id="step_a",
        search_name="GenesByTaxon",
        display_name="Genes by Taxon",
        record_type="transcript",
        step_type=StepType.LEAF,
        parameters={
            "organism": '["pfal", "pvivax"]',
            "min_expression": "2.5",
            "tissue": "blood",
        },
    )

    specs = {
        "organism": ParamSpecNormalized(
            name="organism",
            param_type="treebox-enum-param",
            display_type="treeBox",
            vocabulary=[
                {"value": "pfal", "label": "P. falciparum"},
                {"value": "pvivax", "label": "P. vivax"},
            ],
            help="Pick one or more organisms",
            allow_empty_value=False,
            dependent_params=("geneBooleanFilter",),
        ),
        "min_expression": ParamSpecNormalized(
            name="min_expression",
            param_type="number",
            display_type="",
            is_number=True,
            min_value=0.0,
            max_value=100.0,
            increment=0.1,
        ),
        "tissue": ParamSpecNormalized(
            name="tissue",
            param_type="string-param",
            display_type="",
            max_length=64,
            help="Target tissue type",
        ),
    }

    converted = _convert_step(step_input, param_specs=specs)

    assert set(converted.parameters.keys()) == {"organism", "min_expression", "tissue"}

    # Organism — TreeBox, vocabulary, dependent params.
    organism = converted.parameters["organism"]
    assert organism.param_type == "treebox-enum-param"
    assert organism.options == ["pfal", "pvivax"]
    assert organism.constraints is not None
    assert organism.constraints["displayType"] == "treeBox"
    assert organism.depends_on == ["geneBooleanFilter"]
    assert organism.description == "Pick one or more organisms"
    assert organism.required is True
    assert organism.status == ParamStatus.SET

    # Numeric param — isNumber + bounds.
    min_expr = converted.parameters["min_expression"]
    assert min_expr.param_type == "number"
    assert min_expr.constraints is not None
    assert min_expr.constraints["isNumber"] is True
    assert min_expr.constraints["minValue"] == 0.0
    assert min_expr.constraints["maxValue"] == 100.0
    assert min_expr.constraints["increment"] == 0.1
    # No displayType means no "displayType" key.
    assert "displayType" not in min_expr.constraints
    # No vocabulary → options must be None.
    assert min_expr.options is None

    # String param with max_length — constraints carry maxLength.
    tissue = converted.parameters["tissue"]
    assert tissue.param_type == "string-param"
    assert tissue.constraints is not None
    assert tissue.constraints["maxLength"] == 64
    assert tissue.description == "Target tissue type"

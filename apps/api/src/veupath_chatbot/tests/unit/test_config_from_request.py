"""Test config_from_request passes all fields through.

Characterization tests covering every non-trivial transformation in the
transport→service config adapter.
"""

import pytest

from veupath_chatbot.services.experiment.types.core import DEFAULT_STEP_ANALYSIS_PHASES
from veupath_chatbot.transport.http.routers.experiments._config import (
    config_from_request,
)
from veupath_chatbot.transport.http.schemas.experiments import (
    CreateExperimentRequest,
    OperatorKnobRequest,
    OptimizationSpecRequest,
    ThresholdKnobRequest,
)

# -- Helpers ----------------------------------------------------------------

_BASE_KWARGS: dict[str, object] = {
    "siteId": "PlasmoDB",
    "recordType": "gene",
    "searchName": "GenesByTaxon",
    "parameters": {},
    "positiveControls": ["G1"],
    "negativeControls": [],
    "controlsSearchName": "GeneByLocusTag",
    "controlsParamName": "ds_gene_ids",
}


def _make_req(**overrides: object) -> CreateExperimentRequest:
    return CreateExperimentRequest(**{**_BASE_KWARGS, **overrides})


# -- Passthrough fields -----------------------------------------------------


def test_passthrough_fields():
    req = _make_req(name="my exp", description="desc", mode="single")
    cfg = config_from_request(req)
    assert cfg.site_id == "PlasmoDB"
    assert cfg.record_type == "gene"
    assert cfg.search_name == "GenesByTaxon"
    assert cfg.positive_controls == ["G1"]
    assert cfg.negative_controls == []
    assert cfg.controls_search_name == "GeneByLocusTag"
    assert cfg.controls_param_name == "ds_gene_ids"
    assert cfg.name == "my exp"
    assert cfg.description == "desc"
    assert cfg.mode == "single"


def test_target_gene_ids_passed():
    cfg = config_from_request(_make_req(targetGeneIds=["G1", "G2", "G3"]))
    assert cfg.target_gene_ids == ["G1", "G2", "G3"]


def test_target_gene_ids_default_none():
    cfg = config_from_request(_make_req())
    assert cfg.target_gene_ids is None


# -- optimization_objective: None → "balanced_accuracy" ---------------------


def test_optimization_objective_default():
    cfg = config_from_request(_make_req())
    assert cfg.optimization_objective == "balanced_accuracy"


def test_optimization_objective_explicit():
    cfg = config_from_request(_make_req(optimizationObjective="f1"))
    assert cfg.optimization_objective == "f1"


# -- step_analysis_phases: None → DEFAULT_STEP_ANALYSIS_PHASES -------------


def test_step_analysis_phases_default():
    cfg = config_from_request(_make_req())
    assert cfg.step_analysis_phases == list(DEFAULT_STEP_ANALYSIS_PHASES)


def test_step_analysis_phases_explicit():
    cfg = config_from_request(_make_req(stepAnalysisPhases=["sensitivity"]))
    assert cfg.step_analysis_phases == ["sensitivity"]


# -- parameter_display_values: stringify keys and values --------------------


def test_parameter_display_values_stringify():
    cfg = config_from_request(
        _make_req(parameterDisplayValues={"organism": "P. falciparum", "count": 42})
    )
    assert cfg.parameter_display_values == {"organism": "P. falciparum", "count": "42"}


def test_parameter_display_values_none():
    cfg = config_from_request(_make_req())
    assert cfg.parameter_display_values is None


# -- optimization_specs: request type → service type ------------------------


def test_optimization_specs_conversion():
    specs = [
        OptimizationSpecRequest(name="threshold", type="numeric", min=0, max=1, step=0.1),
        OptimizationSpecRequest(name="mode", type="categorical", choices=["A", "B"]),
    ]
    cfg = config_from_request(_make_req(optimizationSpecs=specs))
    assert cfg.optimization_specs is not None
    assert len(cfg.optimization_specs) == 2
    assert cfg.optimization_specs[0].name == "threshold"
    assert cfg.optimization_specs[0].type == "numeric"
    assert cfg.optimization_specs[0].min == 0
    assert cfg.optimization_specs[0].max == 1
    assert cfg.optimization_specs[0].step == 0.1
    assert cfg.optimization_specs[1].name == "mode"
    assert cfg.optimization_specs[1].choices == ["A", "B"]


def test_optimization_specs_none():
    cfg = config_from_request(_make_req())
    assert cfg.optimization_specs is None


# -- threshold_knobs: request→service type + empty→None --------------------


def test_threshold_knobs_conversion():
    knobs = [
        ThresholdKnobRequest(stepId="s1", paramName="p", minVal=0, maxVal=10, stepSize=1),
    ]
    cfg = config_from_request(_make_req(thresholdKnobs=knobs))
    assert cfg.threshold_knobs is not None
    assert len(cfg.threshold_knobs) == 1
    assert cfg.threshold_knobs[0].step_id == "s1"
    assert cfg.threshold_knobs[0].param_name == "p"
    assert cfg.threshold_knobs[0].min_val == 0
    assert cfg.threshold_knobs[0].max_val == 10
    assert cfg.threshold_knobs[0].step_size == 1


def test_threshold_knobs_none():
    cfg = config_from_request(_make_req())
    assert cfg.threshold_knobs is None


# -- operator_knobs: request→service type + empty→None ---------------------


def test_operator_knobs_conversion():
    knobs = [
        OperatorKnobRequest(combineNodeId="c1", options=["INTERSECT", "UNION"]),
    ]
    cfg = config_from_request(_make_req(operatorKnobs=knobs))
    assert cfg.operator_knobs is not None
    assert len(cfg.operator_knobs) == 1
    assert cfg.operator_knobs[0].combine_node_id == "c1"
    assert cfg.operator_knobs[0].options == ["INTERSECT", "UNION"]


def test_operator_knobs_none():
    cfg = config_from_request(_make_req())
    assert cfg.operator_knobs is None


# -- enrichment_types: defensive copy (list) --------------------------------


def test_enrichment_types():
    cfg = config_from_request(_make_req(enrichmentTypes=["go_function", "pathway"]))
    assert cfg.enrichment_types == ["go_function", "pathway"]
    assert isinstance(cfg.enrichment_types, list)


# -- Cross-validated round-trip: every field has a sane default -------------


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("enable_cross_validation", False),
        ("k_folds", 5),
        ("optimization_budget", 30),
        ("enable_step_analysis", False),
        ("tree_optimization_objective", "precision_at_50"),
        ("tree_optimization_budget", 50),
        ("sort_direction", "ASC"),
        ("controls_value_format", "newline"),
    ],
)
def test_default_values(field: str, expected: object):
    cfg = config_from_request(_make_req())
    assert getattr(cfg, field) == expected

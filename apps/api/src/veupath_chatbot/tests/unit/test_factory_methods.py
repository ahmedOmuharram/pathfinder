"""Tests for factory methods on ControlsContext and IntersectionConfig.

TDD Red: these tests define the expected behavior of factory classmethods
that eliminate duplicated construction boilerplate.
"""

from dataclasses import replace
from unittest.mock import MagicMock

import optuna

from veupath_chatbot.services.control_tests import IntersectionConfig
from veupath_chatbot.services.experiment.helpers import ControlsContext
from veupath_chatbot.services.experiment.types import (
    ExperimentConfig,
)
from veupath_chatbot.services.parameter_optimization.trials import _TrialContext


def _make_config(**overrides: object) -> ExperimentConfig:
    """Build a minimal ExperimentConfig for testing."""
    defaults: dict[str, object] = {
        "site_id": "PlasmoDB",
        "record_type": "transcript",
        "search_name": "GenesByTaxon",
        "parameters": {"organism": "Plasmodium falciparum 3D7"},
        "positive_controls": ["PF3D7_0100100", "PF3D7_0100200"],
        "negative_controls": ["PF3D7_9999901"],
        "controls_search_name": "GeneByLocusTag",
        "controls_param_name": "ds_gene_ids",
        "controls_value_format": "newline",
    }
    defaults.update(overrides)
    return ExperimentConfig(**defaults)

# ---------------------------------------------------------------------------
# ControlsContext.from_config
# ---------------------------------------------------------------------------


class TestControlsContextFromConfig:
    def test_maps_all_fields_from_config(self) -> None:
        config = _make_config()
        ctx = ControlsContext.from_config(config)

        assert ctx.site_id == "PlasmoDB"
        assert ctx.record_type == "transcript"
        assert ctx.controls_search_name == "GeneByLocusTag"
        assert ctx.controls_param_name == "ds_gene_ids"
        assert ctx.controls_value_format == "newline"
        assert ctx.positive_controls == ["PF3D7_0100100", "PF3D7_0100200"]
        assert ctx.negative_controls == ["PF3D7_9999901"]

    def test_empty_controls_stay_empty(self) -> None:
        config = _make_config(positive_controls=[], negative_controls=[])
        ctx = ControlsContext.from_config(config)

        assert ctx.positive_controls == []
        assert ctx.negative_controls == []

    def test_returns_new_instance_each_call(self) -> None:
        config = _make_config()
        ctx1 = ControlsContext.from_config(config)
        ctx2 = ControlsContext.from_config(config)
        assert ctx1 is not ctx2
        assert ctx1 == ctx2

    def test_dataclass_replace_overrides_controls(self) -> None:
        """Verify dataclasses.replace works for fold-level overrides."""
        config = _make_config()
        ctx = ControlsContext.from_config(config)
        fold_ctx = replace(
            ctx,
            positive_controls=["FOLD_POS"],
            negative_controls=["FOLD_NEG"],
        )
        assert fold_ctx.positive_controls == ["FOLD_POS"]
        assert fold_ctx.negative_controls == ["FOLD_NEG"]
        # Original unchanged
        assert ctx.positive_controls == ["PF3D7_0100100", "PF3D7_0100200"]


# ---------------------------------------------------------------------------
# IntersectionConfig.from_experiment_config
# ---------------------------------------------------------------------------


class TestIntersectionConfigFromExperimentConfig:
    def test_maps_fields_with_name_translation(self) -> None:
        config = _make_config()
        ic = IntersectionConfig.from_experiment_config(config)

        assert ic.site_id == "PlasmoDB"
        assert ic.record_type == "transcript"
        assert ic.target_search_name == "GenesByTaxon"
        assert ic.target_parameters == {"organism": "Plasmodium falciparum 3D7"}
        assert ic.controls_search_name == "GeneByLocusTag"
        assert ic.controls_param_name == "ds_gene_ids"
        assert ic.controls_value_format == "newline"

    def test_override_target_parameters(self) -> None:
        config = _make_config()
        modified = {"organism": "Plasmodium vivax"}
        ic = IntersectionConfig.from_experiment_config(
            config, target_parameters=modified
        )
        assert ic.target_parameters == modified
        # Other fields still from config
        assert ic.target_search_name == "GenesByTaxon"

    def test_defaults_preserved(self) -> None:
        config = _make_config()
        ic = IntersectionConfig.from_experiment_config(config)
        # Optional fields should keep dataclass defaults
        assert ic.controls_extra_parameters is None
        assert ic.id_field is None


# ---------------------------------------------------------------------------
# IntersectionConfig.from_controls_context
# ---------------------------------------------------------------------------


class TestIntersectionConfigFromControlsContext:
    def test_maps_controls_fields_and_accepts_target(self) -> None:
        ctx = ControlsContext(
            site_id="ToxoDB",
            record_type="transcript",
            controls_search_name="GeneByLocusTag",
            controls_param_name="ds_gene_ids",
            controls_value_format="newline",
            positive_controls=["TGME49_001"],
            negative_controls=["TGME49_999"],
        )
        ic = IntersectionConfig.from_controls_context(
            ctx,
            target_search_name="GenesByTaxon",
            target_parameters={"organism": "Toxoplasma gondii ME49"},
        )

        assert ic.site_id == "ToxoDB"
        assert ic.record_type == "transcript"
        assert ic.target_search_name == "GenesByTaxon"
        assert ic.target_parameters == {"organism": "Toxoplasma gondii ME49"}
        assert ic.controls_search_name == "GeneByLocusTag"
        assert ic.controls_param_name == "ds_gene_ids"
        assert ic.controls_value_format == "newline"

    def test_defaults_preserved(self) -> None:
        ctx = ControlsContext(
            site_id="PlasmoDB",
            record_type="transcript",
            controls_search_name="GeneByLocusTag",
            controls_param_name="ds_gene_ids",
            controls_value_format="newline",
        )
        ic = IntersectionConfig.from_controls_context(
            ctx,
            target_search_name="SomeSearch",
            target_parameters={},
        )
        assert ic.controls_extra_parameters is None
        assert ic.id_field is None

    def test_passes_through_extra_parameters_and_id_field(self) -> None:
        ctx = ControlsContext(
            site_id="PlasmoDB",
            record_type="transcript",
            controls_search_name="GeneByLocusTag",
            controls_param_name="ds_gene_ids",
            controls_value_format="newline",
        )
        extra = {"organism": "Plasmodium falciparum 3D7"}
        ic = IntersectionConfig.from_controls_context(
            ctx,
            target_search_name="GenesByTaxon",
            target_parameters={"p": "v"},
            controls_extra_parameters=extra,
            id_field="source_id",
        )
        assert ic.controls_extra_parameters == extra
        assert ic.id_field == "source_id"


# ---------------------------------------------------------------------------
# _TrialContext.build_intersection_config
# ---------------------------------------------------------------------------


def _make_trial_context(**overrides: object) -> _TrialContext:
    """Build a minimal _TrialContext for testing."""
    defaults: dict[str, object] = {
        "site_id": "PlasmoDB",
        "record_type": "transcript",
        "search_name": "GenesByTaxon",
        "fixed_parameters": {"organism": "Plasmodium falciparum 3D7"},
        "parameter_space": [],
        "controls_search_name": "GeneByLocusTag",
        "controls_param_name": "ds_gene_ids",
        "positive_controls": ["PF3D7_0100100"],
        "negative_controls": ["PF3D7_9999901"],
        "controls_value_format": "newline",
        "controls_extra_parameters": None,
        "id_field": None,
        "cfg": MagicMock(),
        "optimization_id": "opt_test",
        "budget": 10,
        "study": optuna.create_study(direction="maximize"),
        "progress_callback": None,
        "check_cancelled": None,
        "start_time": 0.0,
        "trials": [],
    }
    defaults.update(overrides)
    return _TrialContext(**defaults)  # type: ignore[arg-type]


class TestTrialContextBuildIntersectionConfig:
    def test_maps_all_fields(self) -> None:
        ctx = _make_trial_context()
        ic = ctx.build_intersection_config({"p": "v"})

        assert ic.site_id == "PlasmoDB"
        assert ic.record_type == "transcript"
        assert ic.target_search_name == "GenesByTaxon"
        assert ic.target_parameters == {"p": "v"}
        assert ic.controls_search_name == "GeneByLocusTag"
        assert ic.controls_param_name == "ds_gene_ids"
        assert ic.controls_value_format == "newline"
        assert ic.controls_extra_parameters is None
        assert ic.id_field is None

    def test_passes_through_extra_parameters_and_id_field(self) -> None:
        extra = {"scope": "all"}
        ctx = _make_trial_context(
            controls_extra_parameters=extra,
            id_field="source_id",
        )
        ic = ctx.build_intersection_config({"p": "v"})

        assert ic.controls_extra_parameters == extra
        assert ic.id_field == "source_id"

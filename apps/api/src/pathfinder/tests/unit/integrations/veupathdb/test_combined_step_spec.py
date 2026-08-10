import pytest
from pydantic import ValidationError

from pathfinder.domain.strategy.ops import BOOLEAN_OPERATORS, CombineOp
from pathfinder.integrations.veupathdb.wdk_models import CombinedStepSpec


def _spec(**overrides: object) -> CombinedStepSpec:
    return CombinedStepSpec.model_validate(
        {
            "primaryStepId": 1,
            "secondaryStepId": 2,
            "booleanOperator": "INTERSECT",
            **overrides,
        }
    )


class TestOperator:
    def test_accepts_every_boolean_operator(self) -> None:
        for operator in BOOLEAN_OPERATORS:
            assert _spec(booleanOperator=operator.value).boolean_operator is operator

    def test_rejects_colocate(self) -> None:
        # COLOCATE is not a boolean operator: WDK does it through
        # GenesBySpanLogic, so it must never reach the boolean search.
        with pytest.raises(ValidationError, match="COLOCATE"):
            _spec(booleanOperator="COLOCATE")

    def test_rejects_an_operator_wdk_does_not_have(self) -> None:
        # Reached WDK unchecked before: control_tests config types this as a
        # plain str, so a typo used to surface as an opaque WDK error.
        with pytest.raises(ValidationError):
            _spec(booleanOperator="INTERSCET")

    def test_a_plain_string_becomes_the_enum(self) -> None:
        assert _spec(booleanOperator="UNION").boolean_operator is CombineOp.UNION


class TestDisplayFields:
    def test_inherits_the_patch_spec_display_fields(self) -> None:
        # The old signature took these as a separate spec_overrides argument,
        # so a combine could carry a display name two different ways.
        spec = _spec(customName="INTERSECT controls")
        assert spec.custom_name == "INTERSECT controls"

    def test_display_fields_are_optional(self) -> None:
        assert _spec().custom_name is None

    def test_weight_defaults_to_unset(self) -> None:
        assert _spec().wdk_weight is None

    def test_weight_is_carried(self) -> None:
        assert _spec(wdkWeight=7).wdk_weight == 7


class TestInputs:
    def test_both_inputs_are_required(self) -> None:
        with pytest.raises(ValidationError):
            CombinedStepSpec.model_validate({"booleanOperator": "INTERSECT"})

    def test_inputs_are_carried(self) -> None:
        spec = _spec(primaryStepId=41, secondaryStepId=42)
        assert (spec.primary_step_id, spec.secondary_step_id) == (41, 42)

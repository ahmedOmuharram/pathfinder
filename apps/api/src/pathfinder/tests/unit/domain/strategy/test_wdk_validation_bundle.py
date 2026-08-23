"""A validation bundle is what WDK sent, and an absent one is not a verdict.

``getValidationBundleJson`` writes ``level`` and ``isValid`` unconditionally
and adds ``errors`` only when the claim is negative.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from pathfinder.devtools.wdk_fixtures import load_recorded
from pathfinder.domain.strategy.validation import StepValidation
from pathfinder.integrations.veupathdb.wdk_models import WDKStep


class TestWdkValid001TheBundleIsLevelAndIsValid:
    def test_wdk_valid_001_a_bundle_states_both_of_its_required_keys(self) -> None:
        bundle = StepValidation.model_validate(
            {"level": "SEMANTIC", "isValid": False, "errors": {"general": ["no"]}}
        )

        assert bundle.level == "SEMANTIC"
        assert bundle.is_valid is False

    def test_wdk_valid_001_a_bundle_without_is_valid_is_refused(self) -> None:
        # A renamed or missing key must not read as a positive claim.
        with pytest.raises(PydanticValidationError):
            StepValidation.model_validate({"level": "SEMANTIC"})

    def test_wdk_valid_001_a_bundle_without_a_level_is_refused(self) -> None:
        with pytest.raises(PydanticValidationError):
            StepValidation.model_validate({"isValid": True})

    def test_wdk_valid_001_errors_are_absent_on_a_positive_claim(self) -> None:
        bundle = StepValidation.model_validate({"level": "RUNNABLE", "isValid": True})

        assert bundle.errors is None
        assert bundle.messages() == []

    def test_wdk_valid_001_errors_split_general_from_by_key(self) -> None:
        recorded = load_recorded("refresh_with_a_value_outside_the_vocabulary")
        bundle = StepValidation.model_validate(recorded.json_body())

        assert bundle.is_valid is False
        assert bundle.errors is not None
        assert bundle.errors.by_key == {}
        assert bundle.errors.general == [
            "The passed changed param value 'Nope' is invalid."
        ]

    def test_wdk_valid_001_a_step_carrying_no_bundle_makes_no_claim(self) -> None:
        # Two defaults used to compose an absence of evidence into "valid".
        step = WDKStep.model_validate(
            {"id": 9, "searchName": "GenesByMolecularWeight", "searchConfig": {}}
        )

        assert step.validation is None

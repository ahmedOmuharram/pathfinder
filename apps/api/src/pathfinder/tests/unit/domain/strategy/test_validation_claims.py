"""A validity claim needs its level; absence of a claim is not a verdict."""

from __future__ import annotations

from pathfinder.domain.strategy.validation import StepValidation, StepValidationErrors


class TestAVerdictNeedsALevel:
    def test_invalid_at_a_real_level_is_a_rejection(self) -> None:
        validation = StepValidation(level="SEMANTIC", isValid=False)

        assert validation.rejects()

    def test_invalid_at_level_none_is_not_a_rejection(self) -> None:
        # Nobody checked. Treating this as broken invents a defect.
        validation = StepValidation(level="NONE", isValid=False)

        assert not validation.rejects()

    def test_valid_at_a_real_level_is_not_a_rejection(self) -> None:
        assert not StepValidation(level="SEMANTIC", isValid=True).rejects()


class TestWhetherAnyoneChecked:
    def test_level_none_means_unchecked(self) -> None:
        assert not StepValidation(level="NONE", isValid=True).was_checked()

    def test_a_real_level_means_checked(self) -> None:
        assert StepValidation(level="RUNNABLE", isValid=True).was_checked()

    def test_the_default_is_unchecked(self) -> None:
        # The default must not read as a passing verdict.
        assert not StepValidation(level="NONE", is_valid=False).was_checked()


class TestTheMessages:
    def test_per_parameter_errors_are_reported(self) -> None:
        validation = StepValidation(
            level="SEMANTIC",
            isValid=False,
            errors=StepValidationErrors(byKey={"organism": ["Cannot be empty."]}),
        )

        assert validation.messages() == ["organism: Cannot be empty."]

    def test_general_errors_are_reported(self) -> None:
        validation = StepValidation(
            level="SEMANTIC",
            isValid=False,
            errors=StepValidationErrors(general=["Search is unavailable."]),
        )

        assert validation.messages() == ["Search is unavailable."]

    def test_no_errors_yields_no_messages(self) -> None:
        assert StepValidation(level="SEMANTIC", isValid=True).messages() == []

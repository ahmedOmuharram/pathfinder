"""An input's invalidity reaches its consumer only at ``RUNNABLE``.

Below that level ``AnswerParam.validateValue`` never looks the input up, so a
consumer reported valid at ``SEMANTIC`` has not been asked the question.
"""

from __future__ import annotations

from pathfinder.domain.strategy.graph_model import (
    StepKind,
    StepStatus,
    StrategyStep,
    step_status,
)
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.validation import (
    StepValidation,
    StepValidationErrors,
)

_INPUT_REFUSED = (
    "The step referenced by ID '440085983' is not runnable because: "
    '{"keyedErrors":{},"validationLevel":"RUNNABLE","validationStatus":"INVALID"}'
)


def _combined() -> StrategyStep:
    return StrategyStep(
        id="combine",
        kind=StepKind.COMBINE,
        operator=CombineOp.INTERSECT,
        primary_input_id="left",
        secondary_input_id="right",
    )


class TestWdkValid004TheLevelCarriesTheClaim:
    def test_wdk_valid_004_a_semantic_pass_is_not_a_runnable_pass(self) -> None:
        # The strategy detail answers at SEMANTIC, where the input is never read.
        semantic = StepValidation(level="SEMANTIC", is_valid=True)

        assert semantic.was_checked()
        assert not semantic.rejects()
        assert semantic.level != "RUNNABLE"

    def test_wdk_valid_004_a_refusal_is_keyed_under_the_answer_parameter(self) -> None:
        runnable = StepValidation(
            level="RUNNABLE",
            is_valid=False,
            errors=StepValidationErrors(
                general=[],
                by_key={"bq_left_op_TranscriptRecordClasses": [_INPUT_REFUSED]},
            ),
        )

        # A client reading `general` for structural problems finds nothing.
        assert runnable.errors is not None
        assert runnable.errors.general == []
        assert runnable.messages()[0].startswith("bq_left_op_")

    def test_wdk_valid_004_a_runnable_refusal_makes_the_consumer_invalid(self) -> None:
        runnable = StepValidation(
            level="RUNNABLE",
            is_valid=False,
            errors=StepValidationErrors(by_key={"bq_left_op": [_INPUT_REFUSED]}),
        )

        assert (
            step_status(
                _combined(),
                wdk_step_id=100,
                validation=runnable,
                has_open_params=False,
            )
            is StepStatus.INVALID
        )

    def test_wdk_valid_004_an_unchecked_bundle_is_not_a_refusal(self) -> None:
        # A structural write builds at NONE, which pairs isValid false with
        # nobody having looked.
        unchecked = StepValidation(level="NONE", is_valid=False)

        assert (
            step_status(
                _combined(),
                wdk_step_id=100,
                validation=unchecked,
                has_open_params=False,
            )
            is StepStatus.BUILT
        )

    def test_wdk_valid_004_the_embedded_bundle_is_not_parsed(self) -> None:
        # The input's own bundle is pretty-printed into the message, under
        # different field names. Re-read the input step instead.
        runnable = StepValidation(
            level="RUNNABLE",
            is_valid=False,
            errors=StepValidationErrors(by_key={"bq_left_op": [_INPUT_REFUSED]}),
        )

        message = runnable.messages()[0]

        assert "validationStatus" in message
        assert runnable.errors is not None
        assert list(runnable.errors.by_key) == ["bq_left_op"]

"""One answer to "what state is this step in".

The same question was being asked in four places and answered differently:
``is_built`` from a WDK id, ``defer_incomplete_new_steps`` inferring "draft"
from "push validation failed AND it was never pushed", ``is_computable`` from
the wiring, and the client's own ``isBuilt: false``. That inference is what
produced the first of the stacked 422s - a newly added step with unfilled
required params was not recognisable as a draft, so it was pushed and rejected.

Status is DERIVED here rather than stored on the step. A stored copy is the
same shape of bug as the stale step counts: it would need updating at every
push, param edit and rewire, and any missed path leaves a step claiming to be
built when it is not.
"""

from pathfinder.domain.strategy.graph_model import (
    StepKind,
    StepStatus,
    StrategyStep,
    step_status,
)
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.validation import StepValidation


def _leaf(step_id: str = "a") -> StrategyStep:
    return StrategyStep(id=step_id, kind=StepKind.SEARCH, search_name="GenesByTaxon")


def _combine(step_id: str = "c") -> StrategyStep:
    return StrategyStep(
        id=step_id,
        kind=StepKind.COMBINE,
        primary_input_id="a",
        secondary_input_id="b",
        operator=CombineOp.INTERSECT,
    )


class TestReady:
    def test_a_complete_step_not_yet_pushed_is_ready(self) -> None:
        """Not a draft: pushing is how it stops being unbuilt, so calling it
        a draft would defer it forever."""
        assert (
            step_status(
                _leaf(), wdk_step_id=None, validation=None, has_open_params=False
            )
            is StepStatus.READY
        )

    def test_ready_is_pushable(self) -> None:
        assert StepStatus.READY.is_pushable


class TestDraft:

    def test_unfilled_required_params_make_a_draft(self) -> None:
        """The 422 this exists to prevent: the UI adds the step first and
        collects its parameters second."""
        assert (
            step_status(_leaf(), wdk_step_id=100, validation=None, has_open_params=True)
            is StepStatus.DRAFT
        )

    def test_a_combine_missing_an_input_is_a_draft(self) -> None:
        half_wired = _combine()
        half_wired.secondary_input_id = None

        assert (
            step_status(
                half_wired, wdk_step_id=100, validation=None, has_open_params=False
            )
            is StepStatus.DRAFT
        )

    def test_a_combine_without_an_operator_is_a_draft(self) -> None:
        no_op = _combine()
        no_op.operator = None

        assert (
            step_status(no_op, wdk_step_id=100, validation=None, has_open_params=False)
            is StepStatus.DRAFT
        )


class TestBuilt:
    def test_a_pushed_complete_step_is_built(self) -> None:
        assert (
            step_status(_leaf(), wdk_step_id=100, validation=None, has_open_params=False)
            is StepStatus.BUILT
        )

    def test_a_pushed_wired_combine_is_built(self) -> None:
        assert (
            step_status(
                _combine(), wdk_step_id=300, validation=None, has_open_params=False
            )
            is StepStatus.BUILT
        )

    def test_a_valid_validation_keeps_it_built(self) -> None:
        assert (
            step_status(
                _leaf(),
                wdk_step_id=100,
                validation=StepValidation(is_valid=True),
                has_open_params=False,
            )
            is StepStatus.BUILT
        )


class TestInvalid:
    def test_wdk_rejecting_a_pushed_step_makes_it_invalid(self) -> None:
        assert (
            step_status(
                _leaf(),
                wdk_step_id=100,
                validation=StepValidation(is_valid=False),
                has_open_params=False,
            )
            is StepStatus.INVALID
        )

    def test_a_never_pushed_step_is_not_invalid(self) -> None:
        """Nothing is in WDK to be invalid about."""
        assert (
            step_status(
                _leaf(),
                wdk_step_id=None,
                validation=StepValidation(is_valid=False),
                has_open_params=False,
            )
            is StepStatus.READY
        )


class TestPushability:
    def test_only_a_draft_is_unpushable(self) -> None:
        """The planner skips drafts by definition instead of inferring them."""
        assert not StepStatus.DRAFT.is_pushable
        assert StepStatus.BUILT.is_pushable
        assert StepStatus.INVALID.is_pushable

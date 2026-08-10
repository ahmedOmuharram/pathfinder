"""``build_strategy`` must not answer "call frame_problem first" when FRAME
already ran and left open parameter slots.

Observed on a real 16-step drug-target strategy: FRAME bound all 8 criteria
but left 7 open slots and set ``needs_user``. The Lead called
``build_strategy`` anyway, and the guard raised a ``ModelRetry`` telling it to
re-run FRAME. Re-running FRAME produces the same open slots, so the advice is
unactionable -- only the user can fill them. The turn then died on an OpenAI
``No tool invocation found for tool call ID`` error.

A retry is the right signal when the model can fix the problem itself. It is
the wrong signal for "a human has to answer this".
"""

from __future__ import annotations

import pytest
from pydantic_ai.exceptions import ModelRetry

from pathfinder.ai.lead.sub_agent_dispatch import build_not_ready_message
from pathfinder.domain.strategy.operational_spec import (
    Criterion,
    OpenSlot,
    OperationalSpec,
    SpecStructure,
    StructureNode,
)


def _bound_criterion(cid: str = "kinases") -> Criterion:
    # `bound` is derived from search_name, not settable.
    return Criterion(
        id=cid,
        text="kinase annotations",
        search_name="GenesByInterproDomain",
    )


def _spec_with_open_slots() -> OperationalSpec:
    return OperationalSpec(
        goal="candidate drug targets",
        criteria=[_bound_criterion()],
        structure=SpecStructure(
            root=StructureNode(kind="leaf", criterion_id="kinases")
        ),
        open_slots=[
            OpenSlot(
                criterion_id="kinases",
                param_name="ms_assay",
                question="Which trophozoite mass-spec assay?",
                options=["Assay A", "Assay B"],
            ),
            OpenSlot(criterion_id="kinases", param_name="min_peptides"),
        ],
    )


class TestNoSpecYet:
    def test_tells_the_model_to_frame_first(self) -> None:
        message = build_not_ready_message(None)

        assert "frame_problem" in message

    def test_is_a_retry_the_model_can_act_on(self) -> None:
        # Nothing has run yet, so re-dispatching FRAME is exactly right.
        assert "frame_problem" in build_not_ready_message(None)


class TestOpenSlotsNeedTheUser:
    def test_does_not_send_the_model_back_to_frame(self) -> None:
        message = build_not_ready_message(_spec_with_open_slots())

        assert "frame_problem" not in message, (
            "re-running FRAME regenerates the same open slots; only the user "
            "can fill them"
        )

    def test_names_the_open_parameters(self) -> None:
        message = build_not_ready_message(_spec_with_open_slots())

        assert "ms_assay" in message
        assert "min_peptides" in message

    def test_tells_the_model_to_ask_the_user(self) -> None:
        message = build_not_ready_message(_spec_with_open_slots())

        assert "ask" in message.lower()

    def test_carries_the_question_when_frame_wrote_one(self) -> None:
        message = build_not_ready_message(_spec_with_open_slots())

        assert "Which trophozoite mass-spec assay?" in message


class TestUnboundCriteria:
    def test_a_spec_with_no_criteria_goes_back_to_frame(self) -> None:
        empty = OperationalSpec(goal="x")

        assert "frame_problem" in build_not_ready_message(empty)


def test_the_message_is_raisable_as_model_retry() -> None:
    # The guard still raises; only its wording changes by case.
    with pytest.raises(ModelRetry, match="ms_assay"):
        raise ModelRetry(build_not_ready_message(_spec_with_open_slots()))

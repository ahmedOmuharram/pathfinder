"""A budget that runs out reports what was bound, not that nothing happened.

The sub-agent writes each criterion into the shared draft as it goes, so the
work survives the ceiling. Saying "no result" throws away a usable turn and
tells the Lead to start again.
"""

from __future__ import annotations

from pathfinder.ai.lead.dispatch_messages import frame_result_from_draft
from pathfinder.domain.strategy.operational_spec import Criterion, OperationalSpec


def _spec(*names: str) -> OperationalSpec:
    return OperationalSpec(
        goal="find candidate drug targets",
        criteria=[
            Criterion(id=n, text=n, role="filter", search_name=f"By{n}") for n in names
        ],
    )


class TestABoundCriterionIsReported:
    def test_the_disposition_asks_for_another_pass(self) -> None:
        result = frame_result_from_draft(_spec("a", "b"))

        assert result.disposition == "needs_user"

    def test_the_summary_counts_what_was_bound(self) -> None:
        result = frame_result_from_draft(_spec("a", "b", "c"))

        assert "3" in result.summary

    def test_the_summary_names_the_budget_rather_than_a_failure(self) -> None:
        result = frame_result_from_draft(_spec("a"))

        assert "budget" in result.summary.lower()

    def test_a_criterion_is_named_so_the_work_is_identifiable(self) -> None:
        result = frame_result_from_draft(_spec("kinases"))

        assert "kinases" in result.summary


class TestNothingBoundIsStillNothing:
    def test_an_empty_draft_says_so(self) -> None:
        result = frame_result_from_draft(OperationalSpec(goal="g"))

        assert "no criteria" in result.summary.lower()

    def test_a_missing_draft_says_so(self) -> None:
        result = frame_result_from_draft(None)

        assert result.disposition == "needs_user"

"""One count means the records you got, and an absent count is not zero."""

from __future__ import annotations

import pytest

from pathfinder.integrations.veupathdb.wdk_models import WDKAnswerMeta


class TestTheCountMatchesTheRecords:
    def test_the_view_filtered_display_count_wins(self) -> None:
        meta = WDKAnswerMeta(
            totalCount=2407,
            displayTotalCount=2400,
            viewTotalCount=4,
            displayViewTotalCount=4,
        )

        assert meta.records_returned() == 4

    def test_the_unfiltered_count_is_not_used_when_a_view_filter_applies(self) -> None:
        meta = WDKAnswerMeta(
            totalCount=2407,
            displayTotalCount=2400,
            viewTotalCount=4,
            displayViewTotalCount=4,
        )

        assert meta.records_returned() != meta.total_count

    def test_without_a_view_filter_all_four_agree(self) -> None:
        meta = WDKAnswerMeta(
            totalCount=2407,
            displayTotalCount=2407,
            viewTotalCount=2407,
            displayViewTotalCount=2407,
        )

        assert meta.records_returned() == 2407


class TestAbsenceIsNotZero:
    def test_an_absent_count_falls_back_to_the_next_one(self) -> None:
        meta = WDKAnswerMeta(totalCount=2407)

        assert meta.records_returned() == 2407

    def test_all_absent_raises_rather_than_reporting_zero(self) -> None:
        with pytest.raises(ValueError, match="no result count"):
            WDKAnswerMeta().records_returned()

    def test_a_genuine_zero_is_reported_as_zero(self) -> None:
        meta = WDKAnswerMeta(
            totalCount=0,
            displayTotalCount=0,
            viewTotalCount=0,
            displayViewTotalCount=0,
        )

        assert meta.records_returned() == 0

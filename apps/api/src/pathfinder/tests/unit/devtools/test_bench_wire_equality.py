"""Wire values compare by kind, and exact counts say what a default did."""

from __future__ import annotations

from pathfinder.devtools.resolver_bench import (
    BenchReport,
    Outcome,
    ParamScore,
    wire_equal,
)
from pathfinder.services.catalog.param_intent import Provenance


class TestWireEquality:
    def test_json_object_whitespace_is_not_a_difference(self) -> None:
        assert wire_equal('{"filters": []}', '{"filters":[]}')

    def test_numbers_compare_by_value(self) -> None:
        assert wire_equal("1e-8", "0.00000001")
        assert wire_equal("2", "2.0")

    def test_lists_ignore_order(self) -> None:
        assert wire_equal('["b","a"]', '["a", "b"]')

    def test_a_single_pick_stored_as_a_list_of_one(self) -> None:
        assert wire_equal("Plasmodium berghei ANKA", '["Plasmodium berghei ANKA"]')

    def test_different_values_stay_different(self) -> None:
        assert not wire_equal("80", "90")
        assert not wire_equal('["a"]', '["a","b"]')


class TestExactIsSplitByProvenance:
    def test_the_report_counts_defaults_apart(self) -> None:
        report = BenchReport(
            scores=[
                ParamScore(
                    search_name="S",
                    param_name="p",
                    gold="1",
                    actual="1",
                    outcome=Outcome.EXACT,
                    provenance=Provenance.DEFAULTED,
                ),
                ParamScore(
                    search_name="S",
                    param_name="q",
                    gold="x",
                    actual="x",
                    outcome=Outcome.EXACT,
                    provenance=Provenance.STATED,
                ),
            ]
        )

        assert report.exact_by_provenance() == {
            Provenance.DEFAULTED: 1,
            Provenance.STATED: 1,
        }

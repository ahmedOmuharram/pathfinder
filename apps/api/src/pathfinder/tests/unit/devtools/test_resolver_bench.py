"""A wrong value and an unanswered one score differently."""

from __future__ import annotations

import json
from pathlib import Path

from pathfinder.devtools.resolver_bench import (
    BenchReport,
    GoldStep,
    Outcome,
    load_gold_steps,
    score_step,
)
from pathfinder.domain.parameters.values import (
    MultiPickValue,
    NumberValue,
    SinglePickValue,
)


def _step(**params: str) -> GoldStep:
    return GoldStep(
        strategy="s",
        database="PlasmoDB",
        record_type="transcript",
        search_name="GenesByX",
        label="a label",
        params=params,
    )


class TestOutcomes:
    def test_a_matching_value_is_exact(self) -> None:
        scores = score_step(
            _step(organism="Plasmodium falciparum 3D7"),
            {"organism": SinglePickValue(value="Plasmodium falciparum 3D7")},
            set(),
        )

        assert scores[0].outcome == Outcome.EXACT

    def test_a_different_value_is_wrong(self) -> None:
        scores = score_step(
            _step(organism="Plasmodium falciparum 3D7"),
            {"organism": SinglePickValue(value="Plasmodium vivax P01")},
            set(),
        )

        assert scores[0].outcome == Outcome.WRONG
        assert scores[0].actual == "Plasmodium vivax P01"

    def test_an_open_slot_is_asked(self) -> None:
        scores = score_step(_step(assay="X"), {}, {"assay"})

        assert scores[0].outcome == Outcome.ASKED

    def test_nothing_at_all_is_unset(self) -> None:
        scores = score_step(_step(assay="X"), {}, set())

        assert scores[0].outcome == Outcome.UNSET


class TestListComparison:
    def test_order_does_not_matter(self) -> None:
        scores = score_step(
            _step(samples='["4hr","6hr"]'),
            {"samples": MultiPickValue(values=["6hr", "4hr"])},
            set(),
        )

        assert scores[0].outcome == Outcome.EXACT

    def test_a_missing_element_is_wrong_not_exact(self) -> None:
        # A partial multi-pick searches a narrower question than the gold one.
        scores = score_step(
            _step(samples='["4hr","6hr","8hr"]'),
            {"samples": MultiPickValue(values=["4hr", "6hr"])},
            set(),
        )

        assert scores[0].outcome == Outcome.WRONG

    def test_a_number_compares_by_wire_value(self) -> None:
        scores = score_step(
            _step(fold_change="2"), {"fold_change": NumberValue(value=2)}, set()
        )

        assert scores[0].outcome == Outcome.EXACT


class TestReport:
    def test_rates_sum_to_one(self) -> None:
        report = BenchReport(
            scores=[
                *score_step(_step(a="1"), {"a": NumberValue(value=1)}, set()),
                *score_step(_step(b="1"), {"b": NumberValue(value=2)}, set()),
                *score_step(_step(c="1"), {}, {"c"}),
                *score_step(_step(d="1"), {}, set()),
            ]
        )

        assert report.total == 4
        assert report.rate(Outcome.EXACT) == 0.25
        assert report.rate(Outcome.WRONG) == 0.25

    def test_an_empty_report_does_not_divide_by_zero(self) -> None:
        assert BenchReport().rate(Outcome.EXACT) == 0.0


class TestCorpus:
    def test_it_reads_the_gold_set(self, tmp_path: Path) -> None:
        (tmp_path / "one.json").write_text(
            json.dumps(
                {
                    "database": "PlasmoDB",
                    "prompts": {"precise": "find things"},
                    "ast": {
                        "recordType": "transcript",
                        "root": {
                            "searchName": "boolean_question_Transcript",
                            "parameters": {},
                            "primaryInput": {
                                "searchName": "GenesByX",
                                "parameters": {"organism": "Pf"},
                                "displayName": "X step",
                            },
                        },
                    },
                }
            )
        )

        steps = load_gold_steps(tmp_path)

        assert len(steps) == 1
        assert steps[0].search_name == "GenesByX"
        assert steps[0].label == "X step"
        assert steps[0].goal == "find things"
        assert steps[0].params == {"organism": "Pf"}

    def test_combine_nodes_carry_no_parameters_to_score(self, tmp_path: Path) -> None:
        (tmp_path / "two.json").write_text(
            json.dumps(
                {
                    "database": "PlasmoDB",
                    "ast": {
                        "root": {
                            "searchName": "boolean_question_Transcript",
                            "parameters": {"operator": "INTERSECT"},
                        }
                    },
                }
            )
        )

        assert load_gold_steps(tmp_path) == []

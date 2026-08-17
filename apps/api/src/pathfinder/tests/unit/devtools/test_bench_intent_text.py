"""What the bench hands the resolver as criterion text.

A gold step's label is a phrase written for a strategy listing. Production
hands the resolver a criterion derived from the user's request, which is longer
and states the values. Scoring the first and shipping the second measures the
wrong thing.
"""

from __future__ import annotations

from pathfinder.devtools.bench_corpus import GoldStep
from pathfinder.devtools.resolver_bench import intent_text


def _step(label: str = "SNPs: purifying selection", goal: str = "") -> GoldStep:
    return GoldStep(
        strategy="s",
        database="PlasmoDB",
        record_type="transcript",
        search_name="GenesByNgsSnps",
        label=label,
        goal=goal,
        params={},
    )


class TestTheLabelIsTheDefault:
    def test_it_is_the_label_alone(self) -> None:
        assert intent_text(_step(goal="find genes"), rich=False) == (
            "SNPs: purifying selection"
        )

    def test_it_falls_back_to_the_goal_when_unlabelled(self) -> None:
        assert intent_text(_step(label="", goal="find genes"), rich=False) == (
            "find genes"
        )


class TestRichIntentCarriesTheRequest:
    def test_the_label_is_still_there(self) -> None:
        text = intent_text(_step(goal="dN/dS below 1.3"), rich=True)

        assert "SNPs: purifying selection" in text

    def test_the_request_is_added(self) -> None:
        text = intent_text(_step(goal="dN/dS below 1.3"), rich=True)

        assert "dN/dS below 1.3" in text

    def test_a_missing_request_leaves_the_label_alone(self) -> None:
        assert intent_text(_step(goal=""), rich=True) == "SNPs: purifying selection"

    def test_a_missing_label_leaves_the_request_alone(self) -> None:
        assert intent_text(_step(label="", goal="dN/dS below 1.3"), rich=True) == (
            "dN/dS below 1.3"
        )

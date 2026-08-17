"""A wrong value and an unanswered one score differently."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from pathfinder.devtools import resolver_bench
from pathfinder.devtools.bench_corpus import GoldStep, Proposal, load_gold_steps
from pathfinder.devtools.resolver_bench import (
    BenchReport,
    Outcome,
    format_report,
    run_bench,
    score_step,
)
from pathfinder.devtools.resolver_bench_proposer import render_sheet
from pathfinder.domain.parameters.values import (
    MultiPickValue,
    NumberValue,
    SinglePickValue,
)
from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.services.catalog.param_dag import ParamFetcher
from pathfinder.services.catalog.param_formatting import FilterFieldInfo, ParameterInfo
from pathfinder.services.catalog.param_intent import Provenance
from pathfinder.services.catalog.param_sheet import SheetEntry, build_sheet


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

    def test_the_header_says_how_many_exact_values_are_defaults(self) -> None:
        report = BenchReport(
            scores=[
                *score_step(
                    _step(a="1"),
                    {"a": NumberValue(value=1)},
                    set(),
                    {"a": Provenance.DEFAULTED},
                ),
                *score_step(
                    _step(b="1"),
                    {"b": NumberValue(value=1)},
                    set(),
                    {"b": Provenance.STATED},
                ),
            ]
        )

        assert "of which stated 1, defaulted 1" in format_report(report)

    def test_an_exact_value_with_no_provenance_is_counted_nowhere(self) -> None:
        report = BenchReport(
            scores=score_step(_step(a="1"), {"a": NumberValue(value=1)}, set())
        )

        assert report.exact_by_provenance() == {}

    def test_a_wrong_value_is_counted_by_its_source(self) -> None:
        report = BenchReport(
            scores=[
                *score_step(
                    _step(a="1"),
                    {"a": NumberValue(value=2)},
                    set(),
                    {"a": Provenance.DEFAULTED},
                ),
                *score_step(
                    _step(b="1"),
                    {"b": NumberValue(value=2)},
                    set(),
                    {"b": Provenance.STATED},
                ),
            ]
        )

        text = format_report(report)

        assert "stated          1   <- claimed the request said this" in text
        assert "defaulted       1   <- the search default, disclosable" in text


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


def _vocab_param(
    name: str, values: list[str], *, depends: list[str] | None = None
) -> ParameterInfo:
    return ParameterInfo(
        name=name,
        display_name=name,
        type="single-pick-vocabulary",
        required=True,
        is_visible=True,
        help="",
        value_format="",
        vocab_leaves=[VocabOption(value=v, display=v) for v in values],
        vocab_depends_on=depends,
    )


def _patch_fetch(
    monkeypatch: pytest.MonkeyPatch,
    read: Callable[[dict[str, str]], list[ParameterInfo]],
) -> None:
    def _factory(*_args: str) -> ParamFetcher:
        async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
            return read(context)

        return fetch_at

    monkeypatch.setattr(resolver_bench, "wdk_fetch_at", _factory)


def _stage_param(_context: dict[str, str]) -> list[ParameterInfo]:
    return [_vocab_param("stage", ["trophozoite", "schizont"])]


class TestTheProposerArm:
    async def test_a_proposed_value_binds_as_stated(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_fetch(monkeypatch, _stage_param)

        async def proposer(
            _gold: GoldStep, _sheet: list[SheetEntry], _bound: dict[str, str]
        ) -> Proposal:
            return Proposal(values={"stage": "trophozoite"})

        report = await run_bench([_step(stage="trophozoite")], proposer=proposer)

        [score] = report.scores
        assert score.outcome is Outcome.EXACT
        assert score.provenance is Provenance.STATED

    async def test_the_sheet_carries_the_vocabulary_and_nothing_is_bound_yet(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_fetch(monkeypatch, _stage_param)
        seen: list[SheetEntry] = []
        bound_at_call: list[dict[str, str]] = []

        async def proposer(
            _gold: GoldStep, sheet: list[SheetEntry], bound: dict[str, str]
        ) -> Proposal:
            seen.extend(sheet)
            bound_at_call.append(dict(bound))
            return Proposal()

        await run_bench([_step(stage="trophozoite")], proposer=proposer)

        [entry] = seen
        assert entry.name == "stage"
        assert [o.value for o in entry.vocabulary] == ["trophozoite", "schizont"]
        assert bound_at_call == [{}]

    async def test_a_value_outside_the_vocabulary_is_dropped_and_recorded(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _patch_fetch(monkeypatch, _stage_param)

        async def proposer(
            _gold: GoldStep, _sheet: list[SheetEntry], _bound: dict[str, str]
        ) -> Proposal:
            return Proposal(values={"stage": "ring"})

        log = tmp_path / "bench.json"
        report = await run_bench(
            [_step(stage="trophozoite")], proposer=proposer, log_path=log
        )

        # Passed as an override the value would have bound; the open slot proves
        # it did not reach the walk.
        [score] = report.scores
        assert score.outcome is Outcome.ASKED
        [entry] = json.loads(log.read_text())
        assert entry["invalid"] == [
            {"paramName": "stage", "value": "ring", "reason": "not_in_vocabulary"}
        ]

    async def test_a_name_the_search_does_not_have_is_recorded(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _patch_fetch(monkeypatch, _stage_param)

        async def proposer(
            _gold: GoldStep, _sheet: list[SheetEntry], _bound: dict[str, str]
        ) -> Proposal:
            return Proposal(values={"stage": "schizont", "life_stage": "ring"})

        log = tmp_path / "bench.json"
        report = await run_bench(
            [_step(stage="schizont")], proposer=proposer, log_path=log
        )

        # The walk refuses an unknown override, which would cost the whole step.
        [score] = report.scores
        assert score.outcome is Outcome.EXACT
        [entry] = json.loads(log.read_text())
        assert entry["invalid"] == [
            {"paramName": "life_stage", "value": "ring", "reason": "unknown_parameter"}
        ]

    async def test_a_filter_value_is_not_read_as_a_vocabulary_entry(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # A filter takes a facet expression. The walk resolves it against the
        # ontology, so the sheet's vocabulary does not judge it.
        def read(_context: dict[str, str]) -> list[ParameterInfo]:
            return [
                ParameterInfo(
                    name="samples",
                    display_name="samples",
                    type="filter",
                    required=False,
                    is_visible=True,
                    help="",
                    value_format="",
                    vocab_leaves=[VocabOption(value="a", display="a")],
                    filter_fields=[
                        FilterFieldInfo(
                            term="Sample type",
                            display="Sample type",
                            type="string",
                            values=["blood"],
                        )
                    ],
                )
            ]

        _patch_fetch(monkeypatch, read)

        async def proposer(
            _gold: GoldStep, _sheet: list[SheetEntry], _bound: dict[str, str]
        ) -> Proposal:
            return Proposal(values={"samples": "Sample type=blood"})

        log = tmp_path / "bench.json"
        report = await run_bench([_step(samples="x")], proposer=proposer, log_path=log)

        [score] = report.scores
        assert score.actual is not None
        assert "blood" in score.actual
        [entry] = json.loads(log.read_text())
        assert entry["invalid"] == []

    async def test_the_log_is_written_after_every_step(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _patch_fetch(monkeypatch, _stage_param)
        calls = 0

        async def proposer(
            _gold: GoldStep, _sheet: list[SheetEntry], _bound: dict[str, str]
        ) -> Proposal:
            nonlocal calls
            calls += 1
            if calls > 1:
                message = "the run stops here"
                raise RuntimeError(message)
            return Proposal(values={"stage": "schizont"})

        log = tmp_path / "bench.json"
        with pytest.raises(RuntimeError):
            await run_bench(
                [_step(stage="schizont"), _step(stage="trophozoite")],
                proposer=proposer,
                log_path=log,
            )

        assert len(json.loads(log.read_text())) == 1


class TestDependentVocabularies:
    @staticmethod
    def _read(
        under_defaults: list[str],
    ) -> Callable[[dict[str, str]], list[ParameterInfo]]:
        def read(context: dict[str, str]) -> list[ParameterInfo]:
            fresh = ["mean", "median"] if context.get("samples") else under_defaults
            return [
                _vocab_param("samples", ["s1", "s2"]),
                _vocab_param("stat", fresh, depends=["samples"]),
            ]

        return read

    async def test_only_the_changed_dependent_is_re_proposed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_fetch(monkeypatch, self._read(["average1"]))
        asked: list[list[str]] = []
        bound_at_call: list[dict[str, str]] = []

        async def proposer(
            _gold: GoldStep, sheet: list[SheetEntry], bound: dict[str, str]
        ) -> Proposal:
            asked.append([entry.name for entry in sheet])
            bound_at_call.append(dict(bound))
            if len(asked) == 1:
                return Proposal(values={"samples": "s1", "stat": "average1"})
            return Proposal(values={"stat": "median"})

        report = await run_bench(
            [_step(samples="s1", stat="median")], proposer=proposer
        )

        assert asked == [["samples", "stat"], ["stat"]]
        # The second round is told which parent it already chose.
        assert bound_at_call == [{}, {"samples": "s1"}]
        assert {s.param_name: s.outcome for s in report.scores} == {
            "samples": Outcome.EXACT,
            "stat": Outcome.EXACT,
        }

    async def test_a_first_round_value_still_valid_survives_the_second_round(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _patch_fetch(monkeypatch, self._read(["average1", "mean"]))
        rounds = 0

        async def proposer(
            _gold: GoldStep, _sheet: list[SheetEntry], _bound: dict[str, str]
        ) -> Proposal:
            nonlocal rounds
            rounds += 1
            if rounds == 1:
                return Proposal(
                    values={"samples": "s1", "stat": "mean"}, reason="first"
                )
            return Proposal(values={"stat": None}, reason="second")

        log = tmp_path / "bench.json"
        report = await run_bench(
            [_step(samples="s1", stat="mean")], proposer=proposer, log_path=log
        )

        assert rounds == 2
        assert {s.param_name: s.outcome for s in report.scores} == {
            "samples": Outcome.EXACT,
            "stat": Outcome.EXACT,
        }
        # The rounds are logged apart, so the null does not hide the kept value.
        [entry] = json.loads(log.read_text())
        assert entry["firstRound"] == {
            "values": {"samples": "s1", "stat": "mean"},
            "reason": "first",
        }
        assert entry["secondRound"] == {"values": {"stat": None}, "reason": "second"}
        assert entry["proposal"] == {"samples": "s1", "stat": "mean"}

    async def test_a_dependent_value_off_the_default_vocabulary_is_kept(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # The sheet showed the vocabulary under the search defaults. A value the
        # bound parents allow is not judged against that stale list.
        _patch_fetch(monkeypatch, self._read(["average1"]))
        rounds = 0

        async def proposer(
            _gold: GoldStep, _sheet: list[SheetEntry], _bound: dict[str, str]
        ) -> Proposal:
            nonlocal rounds
            rounds += 1
            if rounds == 1:
                return Proposal(values={"samples": "s1", "stat": "median"})
            return Proposal()

        log = tmp_path / "bench.json"
        report = await run_bench(
            [_step(samples="s1", stat="median")], proposer=proposer, log_path=log
        )

        assert {s.param_name: s.outcome for s in report.scores} == {
            "samples": Outcome.EXACT,
            "stat": Outcome.EXACT,
        }
        [entry] = json.loads(log.read_text())
        assert entry["invalid"] == []

    async def test_naming_a_bound_parent_in_the_second_round_is_not_unknown(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _patch_fetch(monkeypatch, self._read(["average1"]))
        rounds = 0

        async def proposer(
            _gold: GoldStep, _sheet: list[SheetEntry], _bound: dict[str, str]
        ) -> Proposal:
            nonlocal rounds
            rounds += 1
            if rounds == 1:
                return Proposal(values={"samples": "s1", "stat": "average1"})
            return Proposal(values={"samples": "s1", "stat": "median"})

        log = tmp_path / "bench.json"
        await run_bench(
            [_step(samples="s1", stat="median")], proposer=proposer, log_path=log
        )

        [entry] = json.loads(log.read_text())
        assert entry["invalid"] == []


class TestTheRenderedSheet:
    def test_an_option_carries_its_term_and_its_label(self) -> None:
        info = ParameterInfo(
            name="organism",
            display_name="Organism",
            type="multi-pick-vocabulary",
            required=True,
            is_visible=True,
            help="pick a genome",
            value_format="",
            vocab_leaves=[VocabOption(value="pfal", display="P. falciparum")],
            allowed_values_tree="Plasmodium\n  P. falciparum",
        )

        text = render_sheet(build_sheet([info], query=""), {})

        assert "### organism  (Organism)" in text
        assert "- pfal -- P. falciparum" in text
        assert "help: pick a genome" in text
        assert "is_tree=True" in text

    def test_the_bounds_of_a_number_reach_the_model(self) -> None:
        info = ParameterInfo(
            name="fold_change",
            display_name="Fold change",
            type="number",
            required=True,
            is_visible=True,
            help="",
            value_format="",
            is_number=True,
            default_value="2",
            min=1.0,
            max=10.0,
        )

        text = render_sheet(build_sheet([info], query=""), {})

        assert "min=1.0" in text
        assert "max=10.0" in text

    def test_the_shortlist_note_reaches_the_model(self) -> None:
        leaves = [VocabOption(value=f"v{i}", display=f"v{i}") for i in range(400)]
        info = ParameterInfo(
            name="go_typeahead",
            display_name="GO term",
            type="multi-pick-vocabulary",
            required=True,
            is_visible=True,
            help="",
            value_format="",
            vocab_leaves=leaves,
        )

        text = render_sheet(build_sheet([info], query="anything"), {})

        assert "note: 400 values" in text
        assert "(400 values, 200 shown)" in text

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
from pathfinder.domain.parameters.wdk_vocab import VocabOption, WDKVocabTerm
from pathfinder.domain.search import SearchContext
from pathfinder.domain.strategy.validation import StepValidation
from pathfinder.integrations.veupathdb.wdk_models import WDKSearch, WDKSearchResponse
from pathfinder.integrations.veupathdb.wdk_parameters import (
    WDKEnumParam,
    WDKParameter,
    WDKStringParam,
)
from pathfinder.services.catalog.param_dag import ParamFetcher
from pathfinder.services.catalog.param_formatting import (
    FilterFieldInfo,
    ParameterInfo,
    format_param_info_typed,
)
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


def _patch_definition(
    monkeypatch: pytest.MonkeyPatch,
    params: list[WDKParameter],
    properties: dict[str, list[str]] | None = None,
) -> None:
    """Answer the catalog's definition read for the step's search."""

    async def _definition(
        ctx: SearchContext, **_kw: object
    ) -> tuple[WDKSearchResponse, str]:
        return (
            WDKSearchResponse(
                searchData=WDKSearch(
                    urlSegment=ctx.search_name,
                    parameters=params,
                    properties=properties or {},
                ),
                validation=StepValidation(level="NONE", is_valid=False),
            ),
            ctx.record_type,
        )

    monkeypatch.setattr(resolver_bench, "fetch_search_details", _definition)


def _patch_fetch(
    monkeypatch: pytest.MonkeyPatch,
    read: Callable[[dict[str, str]], list[ParameterInfo]],
) -> None:
    def _factory(*_args: str) -> ParamFetcher:
        async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
            return read(context)

        return fetch_at

    monkeypatch.setattr(resolver_bench, "wdk_fetch_at", _factory)
    _patch_definition(monkeypatch, [])


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


def _vocab_term(code: str, display: str) -> WDKVocabTerm:
    return WDKVocabTerm((code, display, None))


_PHYLETIC_DEFINITION: list[WDKParameter] = [
    WDKStringParam(
        name="profile_pattern", is_visible=False, initial_display_value="hsap=1T"
    ),
    WDKStringParam(name="included_species", allow_empty_value=True),
    WDKStringParam(name="excluded_species", allow_empty_value=True),
    WDKEnumParam(
        name="phyletic_term_map",
        type="multi-pick-vocabulary",
        vocabulary=[
            _vocab_term("ALL", "Root"),
            _vocab_term("MAMM", "Mammalia"),
            _vocab_term("hsap", "Homo sapiens REF"),
            _vocab_term("pfal", "Plasmodium falciparum 3D7"),
        ],
    ),
    WDKEnumParam(
        name="phyletic_indent_map",
        type="multi-pick-vocabulary",
        vocabulary=[
            _vocab_term("MAMM", "1"),
            _vocab_term("hsap", "2"),
            _vocab_term("pfal", "1"),
        ],
    ),
]


def _patch_phyletic(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve GenesByOrthologPattern as both a sheet and a definition."""
    _patch_fetch(monkeypatch, lambda _c: format_param_info_typed(_PHYLETIC_DEFINITION))
    _patch_definition(monkeypatch, _PHYLETIC_DEFINITION)


class TestThePhyleticArm:
    """The bench derives the pattern the same way production does."""

    async def test_the_two_lists_score_the_gold_pattern(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_phyletic(monkeypatch)

        async def proposer(
            _gold: GoldStep, _sheet: list[SheetEntry], _bound: dict[str, str]
        ) -> Proposal:
            return Proposal(
                values={
                    "included_species": "Plasmodium falciparum 3D7",
                    "excluded_species": "hsap",
                }
            )

        report = await run_bench(
            [
                _step(
                    profile_pattern="%hsap:N%pfal:Y%",
                    included_species="pfal",
                    excluded_species="hsap",
                )
            ],
            proposer=proposer,
        )

        assert {s.param_name: s.outcome for s in report.scores} == {
            "profile_pattern": Outcome.EXACT,
            "included_species": Outcome.EXACT,
            "excluded_species": Outcome.EXACT,
        }
        assert {s.provenance for s in report.scores} == {Provenance.STATED}

    async def test_an_unknown_species_drops_both_lists_and_is_recorded(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _patch_phyletic(monkeypatch)

        async def proposer(
            _gold: GoldStep, _sheet: list[SheetEntry], _bound: dict[str, str]
        ) -> Proposal:
            return Proposal(
                values={
                    "included_species": "Plasmodium falciparum",
                    "excluded_species": "hsap",
                }
            )

        log = tmp_path / "bench.json"
        report = await run_bench(
            [_step(profile_pattern="%hsap:N%pfal:Y%")], proposer=proposer, log_path=log
        )

        # Nothing was derived, so the published default holds and scores wrong.
        [score] = report.scores
        assert score.outcome is Outcome.WRONG
        [entry] = json.loads(log.read_text())
        assert [i["paramName"] for i in entry["invalid"]] == [
            "excluded_species",
            "included_species",
        ]

    async def test_two_empty_lists_bind_nothing_and_are_recorded(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # The bare wildcard constrains no species, which production refuses.
        _patch_phyletic(monkeypatch)

        async def proposer(
            _gold: GoldStep, _sheet: list[SheetEntry], _bound: dict[str, str]
        ) -> Proposal:
            return Proposal(
                values={"included_species": "n/a", "excluded_species": None}
            )

        log = tmp_path / "bench.json"
        report = await run_bench(
            [_step(profile_pattern="%hsap:N%pfal:Y%")], proposer=proposer, log_path=log
        )

        [score] = report.scores
        assert score.outcome is Outcome.WRONG
        [entry] = json.loads(log.read_text())
        assert [i["paramName"] for i in entry["invalid"]] == [
            "excluded_species",
            "included_species",
        ]


_EC_DEFINITION: list[WDKParameter] = [
    WDKEnumParam(
        name="ec_number_pattern",
        type="single-pick-vocabulary",
        initial_display_value="2.7.11.1",
        vocabulary=[_vocab_term(v, v) for v in ("2.7.-.-", "2.7.11.1", "3.4.21.-")],
    ),
    WDKStringParam(name="ec_wildcard", initial_display_value="N/A"),
]


def _patch_ec(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve GenesByEcNumber, whose two halves one query ORs."""
    _patch_fetch(monkeypatch, lambda _c: format_param_info_typed(_EC_DEFINITION))
    _patch_definition(
        monkeypatch,
        _EC_DEFINITION,
        {"radio-params": ["ec_number_pattern", "ec_wildcard"]},
    )


class TestTheRadioPairArm:
    """The bench switches the free-text half off the same way production does."""

    async def test_a_null_free_text_half_binds_the_off_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_ec(monkeypatch)

        async def proposer(
            _gold: GoldStep, _sheet: list[SheetEntry], _bound: dict[str, str]
        ) -> Proposal:
            return Proposal(values={"ec_number_pattern": "2.7.-.-"})

        report = await run_bench(
            [_step(ec_number_pattern="2.7.-.-", ec_wildcard="N/A")], proposer=proposer
        )

        assert {s.param_name: s.outcome for s in report.scores} == {
            "ec_number_pattern": Outcome.EXACT,
            "ec_wildcard": Outcome.EXACT,
        }

    async def test_a_filled_free_text_half_is_dropped_and_recorded(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _patch_ec(monkeypatch)

        async def proposer(
            _gold: GoldStep, _sheet: list[SheetEntry], _bound: dict[str, str]
        ) -> Proposal:
            return Proposal(
                values={"ec_number_pattern": "2.7.-.-", "ec_wildcard": "2.7.*"}
            )

        log = tmp_path / "bench.json"
        report = await run_bench(
            [_step(ec_number_pattern="2.7.-.-")], proposer=proposer, log_path=log
        )

        # The run continues, so the guard is measured rather than ending the step.
        [score] = report.scores
        assert score.outcome is Outcome.EXACT
        [entry] = json.loads(log.read_text())
        assert entry["invalid"] == [
            {"paramName": "ec_wildcard", "value": "2.7.*", "reason": "radio_pair"}
        ]


_GO_TERM = "GO:0004672 : protein kinase activity"

_TWO_PAIR_DEFINITION: list[WDKParameter] = [
    WDKEnumParam(
        name="go_typeahead",
        type="multi-pick-vocabulary",
        display_type="typeAhead",
        initial_display_value="[]",
        vocabulary=[_vocab_term(_GO_TERM, _GO_TERM)],
    ),
    WDKStringParam(name="go_term", initial_display_value="N/A"),
    *_EC_DEFINITION,
]


def _patch_two_pairs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve a search declaring two ORed pairs."""
    _patch_fetch(monkeypatch, lambda _c: format_param_info_typed(_TWO_PAIR_DEFINITION))
    _patch_definition(
        monkeypatch,
        _TWO_PAIR_DEFINITION,
        {
            "radio-params": [
                "go_typeahead",
                "go_term",
                "ec_number_pattern",
                "ec_wildcard",
            ]
        },
    )


class TestTwoPairsOnOneSearch:
    async def test_a_refused_half_does_not_stop_the_other_pair_binding_off(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _patch_two_pairs(monkeypatch)

        async def proposer(
            _gold: GoldStep, _sheet: list[SheetEntry], _bound: dict[str, str]
        ) -> Proposal:
            return Proposal(
                values={
                    "go_typeahead": _GO_TERM,
                    "go_term": "*kinase*",
                    "ec_number_pattern": "2.7.-.-",
                }
            )

        log = tmp_path / "bench.json"
        report = await run_bench(
            [
                _step(
                    go_typeahead=_GO_TERM,
                    ec_number_pattern="2.7.-.-",
                    ec_wildcard="N/A",
                )
            ],
            proposer=proposer,
            log_path=log,
        )

        assert {s.param_name: s.outcome for s in report.scores} == {
            "go_typeahead": Outcome.EXACT,
            "ec_number_pattern": Outcome.EXACT,
            "ec_wildcard": Outcome.EXACT,
        }
        [entry] = json.loads(log.read_text())
        assert [i["paramName"] for i in entry["invalid"]] == ["go_term"]

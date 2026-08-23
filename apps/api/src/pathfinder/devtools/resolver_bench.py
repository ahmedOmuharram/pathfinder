"""Scores parameter resolution against the verified gold strategies."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import Literal

import httpx
from assistant_core.platform.pydantic_base import CamelModel
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError
from pydantic_ai.exceptions import AgentRunError

from pathfinder.devtools.bench_corpus import (
    GoldStep,
    Proposer,
    load_gold_steps,
    site_id_for,
)
from pathfinder.devtools.resolver_bench_proposer import propose_with_model
from pathfinder.domain.parameters.phyletic import PhyleticBinding
from pathfinder.domain.parameters.values import ParamValue, to_wire
from pathfinder.domain.parameters.wdk_vocab import match_exact_option
from pathfinder.domain.search import SearchContext
from pathfinder.platform.errors import AppError
from pathfinder.services.catalog.param_dag import (
    ParamFetcher,
    ResolvedParams,
    resolve_params_with_intent,
    wdk_fetch_at,
)
from pathfinder.services.catalog.param_discovery import fetch_search_details
from pathfinder.services.catalog.param_formatting import (
    PHYLETIC_LIST_PARAMS,
    ParameterInfo,
)
from pathfinder.services.catalog.param_intent import ParamIntent, Provenance
from pathfinder.services.catalog.param_phyletic import (
    derive_phyletic_overrides,
    is_phyletic_sheet,
)
from pathfinder.services.catalog.param_sheet import SheetEntry, build_sheet
from pathfinder.services.catalog.radio_pairs import check_radio_pairs, radio_pairs
from pathfinder.services.wdk import WDKSearch


class Outcome(StrEnum):
    """How one gold parameter compares to what resolution produced."""

    EXACT = "exact"
    WRONG = "wrong"
    ASKED = "asked"
    UNSET = "unset"


class ParamScore(CamelModel):
    """The verdict for one gold parameter, and why the value was held."""

    search_name: str
    param_name: str
    gold: str
    actual: str | None
    outcome: Outcome
    provenance: Provenance | None = None


class BenchReport(CamelModel):
    """Aggregate scores over a corpus run."""

    scores: list[ParamScore] = Field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.scores)

    def count(self, outcome: Outcome) -> int:
        return sum(1 for s in self.scores if s.outcome == outcome)

    def rate(self, outcome: Outcome) -> float:
        return (self.count(outcome) / self.total) if self.total else 0.0

    def exact_by_provenance(self) -> dict[Provenance, int]:
        """How many exact values each source produced. A default is not a reading."""
        counts: Counter[Provenance] = Counter()
        for s in self.scores:
            if s.outcome == Outcome.EXACT and s.provenance is not None:
                counts[s.provenance] += 1
        return dict(counts)

    def by_search(self) -> dict[str, Counter[str]]:
        out: dict[str, Counter[str]] = {}
        for s in self.scores:
            out.setdefault(s.search_name, Counter())[s.outcome] += 1
        return out


def score_step(
    step: GoldStep,
    resolved: dict[str, ParamValue],
    asked: set[str],
    provenance: dict[str, Provenance] | None = None,
) -> list[ParamScore]:
    """Compare one step's gold parameters to what resolution produced."""
    scores: list[ParamScore] = []
    for name, gold in step.params.items():
        value = resolved.get(name)
        actual = to_wire(value) if value is not None else None
        if actual is not None:
            outcome = Outcome.EXACT if wire_equal(actual, gold) else Outcome.WRONG
        elif name in asked:
            outcome = Outcome.ASKED
        else:
            outcome = Outcome.UNSET
        scores.append(
            ParamScore(
                search_name=step.search_name,
                param_name=name,
                gold=gold,
                actual=actual,
                outcome=outcome,
                provenance=(provenance or {}).get(name),
            )
        )
    return scores


class _Wire(BaseModel):
    """One wire value read by kind, so two encodings of one value compare equal."""

    model_config = ConfigDict(frozen=True)
    kind: Literal["list", "object", "number", "text"]
    # The value as its comparable parts. Every kind but a list holds one part.
    key: tuple[str, ...]

    @classmethod
    def read(cls, raw: str) -> _Wire:
        text = raw.strip()
        try:
            parsed = json.loads(text)
        except ValueError:
            parsed = None
        if isinstance(parsed, list):
            return cls(kind="list", key=tuple(sorted(str(v) for v in parsed)))
        if isinstance(parsed, dict):
            return cls(
                kind="object",
                key=(json.dumps(parsed, sort_keys=True, separators=(",", ":")),),
            )
        try:
            return cls(kind="number", key=(repr(float(text)),))
        except ValueError:
            return cls(kind="text", key=(text,))


def wire_equal(actual: str, gold: str) -> bool:
    """Two wire encodings of the same value are the same value."""
    a, g = _Wire.read(actual), _Wire.read(gold)
    if a == g:
        return True
    # A single pick reaches the wire either bare or as a list of one.
    return {a.kind, g.kind} == {"list", "text"} and a.key == g.key


def format_report(report: BenchReport) -> str:
    """Render the aggregate counts and the searches that score worst."""
    by_prov = report.exact_by_provenance()
    sources = ", ".join(f"{p} {by_prov[p]}" for p in Provenance if p in by_prov)
    lines = [
        f"gold parameters scored: {report.total}",
        f"  exact  {report.count(Outcome.EXACT):4}  ({report.rate(Outcome.EXACT):5.1%})",
        f"         of which {sources or 'none records a source'}",
        f"  wrong  {report.count(Outcome.WRONG):4}  ({report.rate(Outcome.WRONG):5.1%})"
        "   <- bound a different value",
        f"  asked  {report.count(Outcome.ASKED):4}  ({report.rate(Outcome.ASKED):5.1%})",
        f"  unset  {report.count(Outcome.UNSET):4}  ({report.rate(Outcome.UNSET):5.1%})",
    ]
    worst = sorted(
        report.by_search().items(),
        key=lambda kv: kv[1][Outcome.WRONG],
        reverse=True,
    )
    wrong_examples = [
        s
        for s in report.scores
        if s.outcome == Outcome.WRONG and s.provenance is Provenance.STATED
    ]
    by_source: Counter[Provenance | None] = Counter(
        s.provenance for s in report.scores if s.outcome == Outcome.WRONG
    )
    lines.append("\nwrong values by where the value came from:")
    for source, n in by_source.most_common():
        note = (
            "   <- claimed the request said this"
            if source is Provenance.STATED
            else "   <- the search default, disclosable"
            if source is Provenance.DEFAULTED
            else ""
        )
        lines.append(f"  {source or 'unrecorded':12} {n:4}{note}")
    lines.append("\nwrong values we claimed the request stated:")
    lines.extend(
        f"  {s.param_name:34} gold={s.gold[:34]!r:38} got={str(s.actual)[:34]!r}"
        for s in wrong_examples[:25]
    )
    lines.append("\nsearches with the most wrong values:")
    for search, counts in worst[:10]:
        if not counts[Outcome.WRONG]:
            break
        lines.append(
            f"  {counts[Outcome.WRONG]:3} wrong / {sum(counts.values()):3} params  {search}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def intent_text(step: GoldStep, *, rich: bool) -> str:
    """The criterion text handed to resolution for one gold step.

    The label alone is what a strategy listing shows. ``rich`` adds the
    request behind the strategy, which is the shape production resolves from.
    """
    if not rich or not step.goal:
        return step.label or step.goal
    if not step.label:
        return step.goal
    return f"{step.label} | {step.goal}"


# ---------------------------------------------------------------------------
# The model-proposes arm
# ---------------------------------------------------------------------------


class InvalidProposal(CamelModel):
    """A proposed value the search refuses. Production answers it with a ModelRetry."""

    param_name: str
    value: str | list[str] | None = None
    reason: Literal["unknown_parameter", "not_in_vocabulary", "radio_pair"]


class Checked(CamelModel):
    """What the search made of one set of proposals."""

    overrides: dict[str, str | list[str]] = Field(default_factory=dict)
    invalid: list[InvalidProposal] = Field(default_factory=list)


class ProposalRound(CamelModel):
    """One proposer pass. The log keeps what the model wrote and why; the
    overrides and refusals drive the walk."""

    values: dict[str, str | list[str] | None] = Field(default_factory=dict)
    reason: str = ""
    overrides: dict[str, str | list[str]] = Field(default_factory=dict, exclude=True)
    invalid: list[InvalidProposal] = Field(default_factory=list, exclude=True)


class StepProposal(CamelModel):
    """Both proposer rounds of one step and the overrides the walk finally took."""

    first: ProposalRound | None = None
    second: ProposalRound | None = None
    overrides: dict[str, str | list[str]] = Field(default_factory=dict)

    def refused(self) -> list[InvalidProposal]:
        rounds = [r for r in (self.first, self.second) if r is not None]
        return [item for round_ in rounds for item in round_.invalid]


class StepLog(CamelModel):
    """One step of a run, so a wrong value can be read back beside its proposal."""

    index: int
    strategy: str
    search_name: str
    label: str
    first_round: ProposalRound | None = None
    second_round: ProposalRound | None = None
    proposal: dict[str, str | list[str]] = Field(default_factory=dict)
    invalid: list[InvalidProposal] = Field(default_factory=list)
    scores: list[ParamScore] = Field(default_factory=list)
    error: str | None = None


_LOG: TypeAdapter[list[StepLog]] = TypeAdapter(list[StepLog])


def _judged_by_its_vocabulary(info: ParameterInfo, *, on_the_sheet: bool) -> bool:
    """Whether the vocabulary shown here decides this proposal.

    A filter param takes a facet expression, not an entry. A dependent param on
    the first sheet was read under the search defaults, so the fresh vocabulary
    under the bound parents judges it instead.
    """
    if info.param_kind == "filter" or not info.vocabulary():
        return False
    return not (on_the_sheet and info.vocab_depends_on)


def _validate_proposals(
    proposals: Mapping[str, str | list[str] | None],
    infos: list[ParameterInfo],
    *,
    on_the_sheet: bool,
) -> Checked:
    """Keeps the proposals the search can take. A vocabulary value must be an
    entry, by term or by label; anything else is recorded and left to the walk."""
    by_name = {info.name: info for info in infos}
    overrides: dict[str, str | list[str]] = {}
    invalid: list[InvalidProposal] = []
    for name, value in proposals.items():
        info = by_name.get(name)
        if info is None:
            invalid.append(
                InvalidProposal(
                    param_name=name, value=value, reason="unknown_parameter"
                )
            )
            continue
        if value is None or (isinstance(value, list) and not value):
            continue
        wanted = value if isinstance(value, list) else [value]
        options = info.vocabulary()
        if _judged_by_its_vocabulary(info, on_the_sheet=on_the_sheet) and any(
            match_exact_option(options, v) is None for v in wanted
        ):
            invalid.append(
                InvalidProposal(
                    param_name=name, value=value, reason="not_in_vocabulary"
                )
            )
            continue
        overrides[name] = value
    return Checked(overrides=overrides, invalid=invalid)


class _Derived(CamelModel):
    """What one derivation makes of a proposal: values it binds, values it refuses."""

    overrides: dict[str, str] = Field(default_factory=dict)
    invalid: list[InvalidProposal] = Field(default_factory=list)


async def _definition_of(step: GoldStep) -> WDKSearch:
    """The published definition of the step's search, read through the catalog."""
    response, _ = await fetch_search_details(
        SearchContext(site_id_for(step.database), step.record_type, step.search_name)
    )
    return response.search_data


def _radio_round(
    definition: WDKSearch,
    infos: list[ParameterInfo],
    values: Mapping[str, str | list[str] | None],
) -> _Derived:
    """The off value for each free-text half, and the halves the guard refuses.

    A refused proposal is recorded and dropped, so the run measures the guard
    rather than stopping at it.
    """
    overrides, issue = check_radio_pairs(
        radio_pairs(definition.properties), infos, values
    )
    if issue is None:
        return _Derived(overrides=overrides)
    return _Derived(
        overrides=overrides,
        invalid=[
            InvalidProposal(
                param_name=issue.pair.free_text,
                value=values.get(issue.pair.free_text),
                reason="radio_pair",
            )
        ],
    )


def _phyletic_round(
    definition: WDKSearch,
    infos: list[ParameterInfo],
    values: Mapping[str, str | list[str] | None],
) -> _Derived | None:
    """The three phyletic values the two species lists derive, or their refusal.

    ``None`` leaves the proposals to the ordinary vocabulary check. The clade
    tree lives on the structural params, which the sheet drops.
    """
    if not is_phyletic_sheet(infos):
        return None
    derived = derive_phyletic_overrides(definition.parameters or [], values)
    if derived is None:
        return None
    if isinstance(derived, PhyleticBinding):
        return _Derived(overrides=derived.model_dump())
    # An unresolved term and an empty selection both state no criterion, which
    # production answers with a retry.
    return _Derived(
        invalid=[
            InvalidProposal(
                param_name=name, value=values[name], reason="not_in_vocabulary"
            )
            for name in sorted(PHYLETIC_LIST_PARAMS)
            if name in values
        ]
    )


async def _propose_round(
    proposer: Proposer,
    step: GoldStep,
    sheet: list[SheetEntry],
    bound: dict[str, str],
    infos: list[ParameterInfo],
    *,
    on_the_sheet: bool,
) -> ProposalRound:
    answer = await proposer(step, sheet, bound)
    definition = await _definition_of(step)
    # A derived list holds a canonical value that names no single entry, so the
    # vocabulary check never sees the two lists.
    phyletic = _phyletic_round(definition, infos, answer.values)
    radio = _radio_round(definition, infos, answer.values)
    refused = {item.param_name for item in radio.invalid}
    judged = {
        name: value
        for name, value in answer.values.items()
        if name not in refused
        and not (phyletic is not None and name in PHYLETIC_LIST_PARAMS)
    }
    checked = _validate_proposals(judged, infos, on_the_sheet=on_the_sheet)
    derived = phyletic or _Derived()
    return ProposalRound(
        values=answer.values,
        reason=answer.reason,
        overrides={**checked.overrides, **derived.overrides, **radio.overrides},
        invalid=[*checked.invalid, *derived.invalid, *radio.invalid],
    )


def _stale_vocabularies(infos: list[ParameterInfo]) -> dict[str, set[str]]:
    """The option set each visible dependent param showed under the search defaults."""
    return {
        info.name: {option.value for option in info.vocabulary()}
        for info in infos
        if info.is_visible and info.vocab_depends_on
    }


def _merge_dependents(
    first: ProposalRound, second: ProposalRound, fresh: list[ParameterInfo]
) -> StepProposal:
    """A valid second-round value wins. A first-round value still in the fresh
    vocabulary holds. Anything else is left to the walk."""
    names = {info.name for info in fresh}
    survivors = _validate_proposals(
        {n: v for n, v in first.overrides.items() if n in names},
        fresh,
        on_the_sheet=False,
    ).overrides
    kept = {n: v for n, v in first.overrides.items() if n not in names}
    return StepProposal(
        first=first,
        second=second,
        overrides={**kept, **survivors, **second.overrides},
    )


async def _reconcile_dependents(
    step: GoldStep,
    fetch: ParamFetcher,
    proposer: Proposer,
    first: ProposalRound,
    resolved: ResolvedParams,
    query: str,
) -> StepProposal:
    """Re-proposes only the dependent params whose vocabulary the bound parents
    change. The model is told the values it already chose."""
    settled = StepProposal(first=first, overrides=first.overrides)
    stale = _stale_vocabularies(await fetch({}))
    if not stale:
        return settled
    context = {name: to_wire(value) for name, value in resolved.params.items()}
    under_parents = await fetch(context)
    changed = [
        info
        for info in under_parents
        if info.name in stale
        and {option.value for option in info.vocabulary()} != stale[info.name]
    ]
    if not changed:
        return settled
    # The parents are named so a proposal that repeats one is not an unknown name.
    parents = {name for info in changed for name in info.vocab_depends_on or []}
    judged = changed + [info for info in under_parents if info.name in parents]
    redecided = {info.name for info in changed}
    second = await _propose_round(
        proposer,
        step,
        build_sheet(changed, query=query),
        {n: v for n, v in context.items() if n not in redecided},
        judged,
        on_the_sheet=False,
    )
    return _merge_dependents(first, second, changed)


async def _propose_and_resolve(
    step: GoldStep,
    fetch: ParamFetcher,
    proposer: Proposer,
    intent: ParamIntent,
    query: str,
) -> tuple[StepProposal, ResolvedParams]:
    """One proposer pass, one walk, and a second of each only when the bound
    parents changed a dependent vocabulary."""
    infos = await fetch({})
    first = await _propose_round(
        proposer, step, build_sheet(infos, query=query), {}, infos, on_the_sheet=True
    )
    resolved = await resolve_params_with_intent(
        fetch_at=fetch, intent=intent, overrides=first.overrides
    )
    proposal = await _reconcile_dependents(
        step, fetch, proposer, first, resolved, query
    )
    if proposal.overrides == first.overrides:
        return proposal, resolved
    resolved = await resolve_params_with_intent(
        fetch_at=fetch, intent=intent, overrides=proposal.overrides
    )
    return proposal, resolved


def _memoized(fetch_at: ParamFetcher) -> ParamFetcher:
    """Reads each parameter context once per step. The walk, the dependent
    re-read and the second walk all want the same payloads."""
    read: dict[tuple[tuple[str, str], ...], list[ParameterInfo]] = {}

    async def memoized(context: dict[str, str]) -> list[ParameterInfo]:
        key = tuple(sorted(context.items()))
        if key not in read:
            read[key] = await fetch_at(context)
        return read[key]

    return memoized


def _step_line(index: int, step: GoldStep, log: StepLog) -> str:
    outcomes = " ".join(f"{s.param_name}={s.outcome}" for s in log.scores)
    refused = " ".join(f"{i.param_name}={i.value!r}" for i in log.invalid)
    return (
        f"  [{index}] {step.search_name}: {outcomes}"
        f"{f'  INVALID {refused}' if refused else ''}"
    )


def _step_log(
    index: int,
    step: GoldStep,
    proposal: StepProposal,
    scores: list[ParamScore],
    error: str | None,
) -> StepLog:
    return StepLog(
        index=index,
        strategy=step.strategy,
        search_name=step.search_name,
        label=step.label,
        first_round=proposal.first,
        second_round=proposal.second,
        proposal=proposal.overrides,
        invalid=proposal.refused(),
        scores=scores,
        error=error,
    )


async def _write_log(log_path: Path | None, entries: list[StepLog]) -> None:
    """Rewrites the log after each step, so an interrupted run still has data."""
    if log_path is None:
        return
    payload = _LOG.dump_json(entries, indent=1, by_alias=True)
    await asyncio.to_thread(log_path.write_bytes, payload)


async def run_bench(
    steps: list[GoldStep],
    *,
    proposer: Proposer | None = None,
    limit: int | None = None,
    rich_intent: bool = False,
    log_path: Path | None = None,
) -> BenchReport:
    """Resolve each step's parameters and score them.

    With a ``proposer`` the model reads the parameter sheet and its values enter
    the walk as overrides, which is the production shape.
    """
    report = BenchReport()
    entries: list[StepLog] = []
    for index, step in enumerate(steps[:limit] if limit else steps):
        site = site_id_for(step.database)
        fetch = _memoized(wdk_fetch_at(site, step.record_type, step.search_name))
        # The propose arm hands the walk the text production hands it: the criterion.
        # The request reaches the model on the sheet instead.
        text = step.label if proposer else intent_text(step, rich=rich_intent)
        intent = ParamIntent(text=text)
        try:
            proposal = StepProposal()
            if proposer is None:
                resolved = await resolve_params_with_intent(
                    fetch_at=fetch, intent=intent, overrides={}
                )
            else:
                proposal, resolved = await _propose_and_resolve(
                    step, fetch, proposer, intent, intent_text(step, rich=True)
                )
        # A step that WDK rejects, times out on, or answers unparseably is
        # recorded and skipped: a corpus run scores what it can reach.
        except (AppError, httpx.HTTPError, ValidationError, AgentRunError) as exc:
            detail = f"{type(exc).__name__}: {exc}"
            print(f"  [{index}] {step.search_name}: {detail}"[:160])
            entries.append(_step_log(index, step, StepProposal(), [], detail[:300]))
            await _write_log(log_path, entries)
            continue
        # An unread param is asked about too: resolution hands it back to be read
        # off the request rather than binding a default.
        asked = {slot.param_name for slot in resolved.open_slots} | set(resolved.unread)
        scores = score_step(
            step, dict(resolved.params), asked, dict(resolved.provenance)
        )
        report.scores.extend(scores)
        entry = _step_log(index, step, proposal, scores, None)
        entries.append(entry)
        await _write_log(log_path, entries)
        print(_step_line(index, step, entry))
    return report


def _parse(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="pathfinder.devtools.resolver_bench")
    parser.add_argument(
        "gold_dir",
        nargs="?",
        type=Path,
        default=Path("../../thesis/eval/gold_strategies"),
    )
    parser.add_argument(
        "--propose",
        action="store_true",
        help="the model proposes every visible parameter from the sheet",
    )
    parser.add_argument(
        "--rich-intent",
        action="store_true",
        help="hand the rules arm the request as well as the step label",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--log", type=Path, default=None, help="per-step JSON log")
    return parser.parse_args(argv)


async def _main() -> None:
    args = _parse(sys.argv[1:])
    steps = load_gold_steps(args.gold_dir)
    arm = "propose" if args.propose else "rules"
    read = (
        "sheet=label+request"
        if args.propose
        else f"intent={'rich' if args.rich_intent else 'label'}"
    )
    print(
        f"corpus: {len(steps)} steps, {sum(len(s.params) for s in steps)} parameters"
        f" | arm={arm} | {read}\n"
    )
    report = await run_bench(
        steps,
        proposer=propose_with_model if args.propose else None,
        limit=args.limit,
        rich_intent=args.rich_intent,
        log_path=args.log,
    )
    print("\n" + format_report(report))


if __name__ == "__main__":
    asyncio.run(_main())

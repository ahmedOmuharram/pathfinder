"""Scores parameter resolution against the verified gold strategies."""

from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter
from collections.abc import Iterable
from enum import StrEnum
from pathlib import Path

from pydantic import Field

from pathfinder.ai.memory.embedding import embed_text
from pathfinder.ai.tools.standalone.frame_spec import (
    pick_from_vocabulary,
    read_free_value,
)
from pathfinder.domain.parameters.values import ParamValue, to_wire
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.services.catalog.param_dag import (
    resolve_params_with_intent,
    wdk_fetch_at,
)
from pathfinder.services.catalog.param_intent import (
    NO_RESOLVERS,
    ParamIntent,
    Provenance,
    ValueResolvers,
)

_COMBINE_MARKER = "boolean_question"

# The seam as the framing agent wires it, so a bench run measures what ships.
LLM_RESOLVERS = ValueResolvers(vocab=pick_from_vocabulary, free=read_free_value)


class Outcome(StrEnum):
    """How one gold parameter compares to what resolution produced."""

    EXACT = "exact"
    WRONG = "wrong"
    ASKED = "asked"
    UNSET = "unset"


class GoldStep(CamelModel):
    """One gold step: the search, its label, and the values it was built with."""

    strategy: str
    database: str
    record_type: str
    search_name: str
    label: str
    goal: str = ""
    params: dict[str, str] = Field(default_factory=dict)


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

    def by_search(self) -> dict[str, Counter[str]]:
        out: dict[str, Counter[str]] = {}
        for s in self.scores:
            out.setdefault(s.search_name, Counter())[s.outcome] += 1
        return out


def load_gold_steps(gold_dir: Path) -> list[GoldStep]:
    """Read every step that carries parameters from the gold strategy files."""
    steps: list[GoldStep] = []
    for path in sorted(gold_dir.glob("*.json")):
        raw = json.loads(path.read_text())
        ast = raw.get("ast")
        if not isinstance(ast, dict):
            continue
        goal = str((raw.get("prompts") or {}).get("precise") or "")
        steps.extend(
            _walk(
                ast.get("root"),
                strategy=path.stem,
                database=str(raw.get("database") or ""),
                record_type=str(ast.get("recordType") or "transcript"),
                goal=goal,
            )
        )
    return steps


def _walk(
    node: object, *, strategy: str, database: str, record_type: str, goal: str
) -> Iterable[GoldStep]:
    if not isinstance(node, dict):
        return
    search = node.get("searchName")
    params = node.get("parameters")
    if (
        isinstance(search, str)
        and _COMBINE_MARKER not in search
        and isinstance(params, dict)
        and params
    ):
        yield GoldStep(
            strategy=strategy,
            database=database,
            record_type=record_type,
            search_name=search,
            label=str(node.get("displayName") or ""),
            goal=goal,
            params={str(k): str(v) for k, v in params.items()},
        )
    for key in ("primaryInput", "secondaryInput"):
        yield from _walk(
            node.get(key),
            strategy=strategy,
            database=database,
            record_type=record_type,
            goal=goal,
        )


def score_step(
    step: GoldStep,
    resolved: dict[str, ParamValue],
    open_slots: set[str],
    provenance: dict[str, Provenance] | None = None,
) -> list[ParamScore]:
    """Compare one step's gold parameters to what resolution produced."""
    scores: list[ParamScore] = []
    for name, gold in step.params.items():
        value = resolved.get(name)
        actual = to_wire(value) if value is not None else None
        if actual is not None:
            outcome = Outcome.EXACT if _same(actual, gold) else Outcome.WRONG
        elif name in open_slots:
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


def _same(actual: str, gold: str) -> bool:
    """Compare two wire values, tolerating list order and surrounding space."""
    a, g = actual.strip(), gold.strip()
    if a == g:
        return True
    a_list, g_list = _as_list(a), _as_list(g)
    if a_list is not None and g_list is not None:
        return sorted(a_list) == sorted(g_list)
    return False


def _as_list(value: str) -> list[str] | None:
    if not value.startswith("["):
        return None
    try:
        parsed = json.loads(value)
    except ValueError:
        return None
    return [str(v) for v in parsed] if isinstance(parsed, list) else None


def format_report(report: BenchReport) -> str:
    """Render the aggregate counts and the searches that score worst."""
    lines = [
        f"gold parameters scored: {report.total}",
        f"  exact  {report.count(Outcome.EXACT):4}  ({report.rate(Outcome.EXACT):5.1%})",
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
    by_source = Counter(str(s.provenance) for s in wrong_examples)
    lines.append("\nwrong values by where the value came from:")
    for source, n in by_source.most_common():
        note = (
            "   <- claimed the request said this"
            if source == Provenance.STATED
            else "   <- the search default, disclosable"
            if source == Provenance.DEFAULTED
            else ""
        )
        lines.append(f"  {source:12} {n:4}{note}")
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


def site_id_for(database: str) -> str:
    """Map a gold strategy's database label to a configured site id."""
    return database.strip().lower().replace(" ", "")


async def run_bench(
    steps: list[GoldStep],
    *,
    resolvers: ValueResolvers = NO_RESOLVERS,
    bind_inferred: bool = False,
    limit: int | None = None,
) -> BenchReport:
    """Resolve each step's parameters from its label and score them."""
    report = BenchReport()
    for index, step in enumerate(steps[:limit] if limit else steps):
        site = site_id_for(step.database)
        try:
            resolved = await resolve_params_with_intent(
                fetch_at=wdk_fetch_at(site, step.record_type, step.search_name),
                intent=ParamIntent(text=step.label or step.goal),
                embed=embed_text,
                resolvers=resolvers,
                bind_inferred=bind_inferred,
            )
        except Exception as exc:  # noqa: BLE001 - a bench records failures, it does not raise
            print(f"  [{index}] {step.search_name}: {type(exc).__name__}: {exc}"[:160])
            continue
        report.scores.extend(
            score_step(
                step,
                dict(resolved.params),
                {slot.param_name for slot in resolved.open_slots},
                dict(resolved.provenance),
            )
        )
    return report


async def _main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    gold = Path(args[0]) if args else Path("../../thesis/eval/gold_strategies")
    steps = load_gold_steps(gold)
    resolvers = LLM_RESOLVERS if "--resolvers" in sys.argv else NO_RESOLVERS
    print(
        f"corpus: {len(steps)} steps, {sum(len(s.params) for s in steps)} parameters"
        f" | resolvers={'on' if resolvers is not NO_RESOLVERS else 'off'}"
        f" | bind_inferred={'--bind-inferred' in sys.argv}\n"
    )
    report = await run_bench(
        steps, resolvers=resolvers, bind_inferred="--bind-inferred" in sys.argv
    )
    print("\n" + format_report(report))


if __name__ == "__main__":
    asyncio.run(_main())

"""The benchmark's proposer arm: one model call reads a search's parameter sheet
and returns a value or null for every visible parameter."""

from __future__ import annotations

from functools import cache

from pydantic_ai import Agent

from pathfinder.devtools.bench_corpus import GoldStep, Proposal
from pathfinder.services.catalog.param_sheet import SheetEntry

MODEL = "openai:gpt-5.6-luna"

INSTRUCTIONS = """\
You are binding ONE criterion of a scientist's gene-search strategy to a VEuPathDB \
search. You are shown the scientist's full request, the criterion this search realizes, \
and every visible parameter of the search with its name, type, help, default, and \
(when it has one) its controlled vocabulary.

For EVERY listed parameter return either a value or null.
- A vocabulary parameter takes a value copied EXACTLY from its listed vocabulary (the part \
before ' -- '). Multi-pick parameters take a JSON list of such values. Never invent one.
- A parameter with no vocabulary takes the literal the request states (a number, an accession, \
a search term). Do not add units or quoting.
- A filter (sample-set) parameter takes null unless the request restricts samples; then \
"<facet>=<value1>,<value2>" using the listed facets.
- Return null when the request does not state or clearly imply a value for that parameter. \
The default then applies and is disclosed. Never guess a value the request does not support.
- When the request DOES state a value (a cutoff, "top 10 percent" -> percentile 90, \
"at least 2 peptides", "non-syntenic" -> no), return it even if it differs from the default.
- For a reference/comparison contrast, the group named as the subject is the comparison; \
the baseline is the reference.
- Two organism-like parameters can mean different things: the genome the search itself \
runs over, and a target organism for orthologs. Read the request for each.
- Values under "Already bound" are decided. Read the parameters you are asked about \
against them; do not contradict them.
"""

_HELP_CHARS = 600
_FACET_VALUES = 25


@cache
def _agent() -> Agent[None, Proposal]:
    return Agent(
        MODEL, output_type=Proposal, instructions=INSTRUCTIONS, name="bench_proposer"
    )


def _facts(entry: SheetEntry) -> str:
    facts = [
        f"type={entry.type}",
        f"required={entry.required}",
        f"is_number={entry.is_number}",
        f"is_tree={entry.is_tree}",
        f"default={entry.default!r}",
    ]
    if entry.min is not None:
        facts.append(f"min={entry.min}")
    if entry.max is not None:
        facts.append(f"max={entry.max}")
    return " ".join(facts)


def _option_line(value: str, display: str) -> str:
    label = f" -- {display}" if display and display != value else ""
    return f"  - {value}{label}"


def _render_entry(entry: SheetEntry) -> str:
    lines = [f"### {entry.name}  ({entry.display_name})", _facts(entry)]
    if entry.help:
        lines.append(f"help: {entry.help[:_HELP_CHARS]}")
    if entry.depends_on:
        lines.append(f"vocabulary depends on: {entry.depends_on}")
    if entry.vocabulary_note:
        lines.append(f"note: {entry.vocabulary_note}")
    if entry.vocabulary:
        lines.append(
            f"vocabulary ({entry.vocabulary_total} values, "
            f"{len(entry.vocabulary)} shown):"
        )
        lines.extend(
            _option_line(option.value, option.display) for option in entry.vocabulary
        )
    elif entry.filter_facets:
        lines.append("filter facets:")
        lines.extend(
            f"  - {facet.term}: {', '.join(facet.values[:_FACET_VALUES])}"
            for facet in entry.filter_facets
        )
    else:
        lines.append("no vocabulary: free value")
    return "\n".join(lines)


def render_sheet(sheet: list[SheetEntry], bound: dict[str, str]) -> str:
    """The sheet as the model reads it: the values already decided, then one block
    per parameter it is asked about."""
    already = (
        "Already bound:\n"
        + "\n".join(f"  {name}={value}" for name, value in sorted(bound.items()))
        + "\n\n"
        if bound
        else ""
    )
    return already + "\n\n".join(_render_entry(entry) for entry in sheet)


async def propose_with_model(
    step: GoldStep, sheet: list[SheetEntry], bound: dict[str, str]
) -> Proposal:
    """One call per sheet: the model proposes a value or null per parameter."""
    prompt = (
        f"Scientist's request:\n{step.goal}\n\n"
        f"Criterion this search realizes: {step.label}\n"
        f"Search: {step.search_name}\n\n"
        f"Parameters:\n\n{render_sheet(sheet, bound)}\n\n"
        f"Return values for: {[entry.name for entry in sheet]}"
    )
    result = await _agent().run(prompt)
    return result.output

"""The parameter sheet a model reads before it proposes values for a search."""

from __future__ import annotations

import re

from pydantic import Field

from pathfinder.domain.parameters.wdk_vocab import (
    VocabOption,
    leading_accession_token,
)
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.services.catalog.param_formatting import FilterFieldInfo, ParameterInfo

# Below this, the whole vocabulary is cheap enough to send and ranking can only
# lose information. 200 options is roughly 4K tokens.
DIRECT_MAX = 200
# The shortlist a large vocabulary is reduced to. Same order as DIRECT_MAX so the
# model sees a comparable amount either way.
TOP_K = 200

_WORD = re.compile(r"[a-z0-9]+")
# An accession carries inner punctuation, so it is read as one token.
_TOKEN = re.compile(r"[a-z0-9][a-z0-9:._-]*")
# Shorter words match everything and rank nothing.
_MIN_WORD_LENGTH = 3


class SheetEntry(CamelModel):
    """One visible parameter with everything needed to propose a value for it."""

    name: str
    display_name: str
    type: str
    required: bool
    is_number: bool = False
    is_tree: bool = False
    help: str = ""
    default: str | None = None
    min: float | None = None
    max: float | None = None
    depends_on: list[str] = Field(default_factory=list)
    vocabulary: list[VocabOption] = Field(default_factory=list)
    vocabulary_total: int = 0
    vocabulary_note: str | None = None
    filter_facets: list[FilterFieldInfo] = Field(default_factory=list)


def _query_words(query: str) -> list[str]:
    return [w for w in _WORD.findall(query.casefold()) if len(w) >= _MIN_WORD_LENGTH]


def _query_tokens(query: str) -> frozenset[str]:
    """The request's words, each kept whole so an accession survives punctuation."""
    return frozenset(token.rstrip(":._-") for token in _TOKEN.findall(query.casefold()))


def _is_named(option: VocabOption, query: str, tokens: frozenset[str]) -> bool:
    """The request writes this option out: its value, its label, or its accession.

    An identifier the user wrote is not a similarity question. It must reach the
    model even when nothing else about the option matches the request.
    """
    if option.value and option.value.casefold() in query:
        return True
    if option.display and option.display.casefold() in query:
        return True
    accession = leading_accession_token(option.value)
    return accession is not None and accession.casefold() in tokens


def _shortlist(options: list[VocabOption], query: str) -> list[VocabOption]:
    """The ``TOP_K`` options whose labels share the most words with the request."""
    low = query.casefold()
    words = _query_words(low)
    tokens = _query_tokens(low)
    ranked = sorted(
        enumerate(options),
        key=lambda pair: (
            not _is_named(pair[1], low, tokens),
            -sum(w in (pair[1].display or pair[1].value).casefold() for w in words),
            pair[0],
        ),
    )
    return [option for _, option in ranked[:TOP_K]]


def _note(info: ParameterInfo, shown: int, total: int) -> str | None:
    parts: list[str] = []
    if total > shown:
        parts.append(
            f"{total} values; the {shown} most relevant to the request by name are "
            f"shown. If the value you need is absent, call get_parameter_options("
            f"search_name, '{info.name}', query='<keyword>') before deciding it does not exist."
        )
    if info.allowed_values_tree is not None:
        parts.append("A parent term selects all of its children.")
    if info.vocab_depends_on:
        parents = ", ".join(info.vocab_depends_on)
        parts.append(
            f"This vocabulary depends on {parents} and is shown under the search defaults; "
            f"it is re-read under the values you propose."
        )
    return " ".join(parts) or None


def build_sheet(infos: list[ParameterInfo], *, query: str) -> list[SheetEntry]:
    """Visible parameters only. A vocabulary over ``DIRECT_MAX`` is shortlisted."""
    entries: list[SheetEntry] = []
    for info in infos:
        if not info.is_visible:
            continue
        options = info.vocabulary()
        shown = options if len(options) <= DIRECT_MAX else _shortlist(options, query)
        entries.append(
            SheetEntry(
                name=info.name,
                display_name=info.display_name,
                type=info.type,
                required=info.required,
                is_number=info.is_number,
                is_tree=info.allowed_values_tree is not None,
                help=info.help,
                default=info.default_value,
                min=info.min,
                max=info.max,
                depends_on=list(info.vocab_depends_on or []),
                vocabulary=shown,
                vocabulary_total=len(options),
                vocabulary_note=_note(info, len(shown), len(options)),
                filter_facets=info.filter_fields,
            )
        )
    return entries

"""The clade tree of ``GenesByOrthologPattern``, the census pattern derived from
a selection, and the two documentation lists the reference client reads back."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from typing import Literal

from pydantic import BaseModel, Field

from pathfinder.domain.parameters.wdk_vocab import VocabOption, WDKVocabTerm

PHYLETIC_PARAM_NAMES = frozenset(
    {
        "profile_pattern",
        "included_species",
        "excluded_species",
        "phyletic_indent_map",
        "phyletic_term_map",
    }
)
"""A search is phyletic when it carries all five of these parameters."""

PHYLETIC_MAP_PARAMS = frozenset({"phyletic_term_map", "phyletic_indent_map"})
"""The two structural parameters that carry the tree. They state no criterion."""

TriState = Literal["include", "exclude"]
"""A species left out of both lists has no third state: the pattern omits it."""

NO_SPECIES = "n/a"
"""The literal the reference client decodes as the empty set."""

NO_CONSTRAINT_PATTERN = "%"
"""The pattern of an empty selection: every census matches it."""

_ROOT_CODE = "ALL"
"""The tree root, which the reference client also writes as ``All Organisms``.
Authoring resolves neither form: a pattern over every species exceeds the
parameter's 4000 character cap and states more than the request means."""

_DEFAULT_DEPTH = 1


class PhyleticNode(BaseModel):
    """One clade or species of the tree, with its children below it."""

    code: str
    label: str
    depth: int
    children: list[PhyleticNode] = Field(default_factory=list)


class ResolvedTerms(BaseModel):
    """The vocabulary codes a proposal named, and the words that named nothing."""

    codes: list[str] = Field(default_factory=list)
    unknown: list[str] = Field(default_factory=list)


class PhyleticBinding(BaseModel):
    """The three parameter values a selection produces.

    The field names are the WDK parameter names, so this model stays snake_case.
    """

    profile_pattern: str
    included_species: str
    excluded_species: str


class PhyleticUnresolved(BaseModel):
    """Why a pair of proposals binds nothing, named per parameter.

    A conflict is a code both proposals claim: the two states contradict, and
    the census has one state per species.
    """

    included_unknown: list[str] = Field(default_factory=list)
    excluded_unknown: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)


def _depth_of(display: str) -> int:
    """The depth the indent map carries in its display field."""
    text = display.strip()
    return int(text) if text.isdigit() else _DEFAULT_DEPTH


class PhyleticTree(BaseModel):
    """The clade tree built from ``phyletic_term_map`` and ``phyletic_indent_map``."""

    roots: list[PhyleticNode] = Field(default_factory=list)

    @classmethod
    def from_vocab(
        cls,
        term_map: Sequence[WDKVocabTerm],
        indent_map: Sequence[WDKVocabTerm],
    ) -> PhyleticTree:
        """Build the tree from the two vocabularies.

        Each entry states its parent term, which is the structure WDK publishes.
        An entry that names no parent, or one the map has not listed yet,
        attaches to the last node shallower than itself in the indent map. The
        synthetic root ``ALL`` is not a selectable node.
        """
        depths = {entry.term: _depth_of(entry.display) for entry in indent_map}
        roots: list[PhyleticNode] = []
        stack: list[PhyleticNode] = []
        by_code: dict[str, PhyleticNode] = {}
        for entry in term_map:
            if not entry.term or entry.term == _ROOT_CODE:
                continue
            depth = depths.get(entry.term, _DEFAULT_DEPTH)
            node = PhyleticNode(
                code=entry.term,
                label=entry.display or entry.term,
                depth=depth,
            )
            while stack and stack[-1].depth >= depth:
                stack.pop()
            stated = by_code.get(entry.parent) if entry.parent else None
            parent = stated or (stack[-1] if stack else None)
            if parent is None:
                roots.append(node)
            else:
                parent.children.append(node)
            by_code[node.code] = node
            stack.append(node)
        return cls(roots=roots)

    def nodes(self) -> Iterator[PhyleticNode]:
        """Every selectable node, in tree order. The root is not one of them."""

        def walk(nodes: list[PhyleticNode]) -> Iterator[PhyleticNode]:
            for node in nodes:
                yield node
                yield from walk(node.children)

        return walk(self.roots)

    def labels(self) -> list[VocabOption]:
        """Every selectable node as a code and its display name, in tree order."""
        return [
            VocabOption(value=node.code, display=node.label) for node in self.nodes()
        ]

    def resolve_terms(self, proposal: str | list[str]) -> ResolvedTerms:
        """Map a proposal to vocabulary codes and report what matched nothing.

        A proposal is a code or a display name, one per list entry or comma
        separated. An exact code wins over a case-insensitive match.
        """
        nodes = list(self.nodes())
        exact = {node.code for node in nodes}
        folded: dict[str, str] = {}
        for node in nodes:
            folded.setdefault(node.code.casefold(), node.code)
        for node in nodes:
            if node.label:
                folded.setdefault(node.label.casefold(), node.code)

        codes: list[str] = []
        unknown: list[str] = []
        for token in _split_proposal(proposal):
            code = token if token in exact else folded.get(token.casefold())
            if code is None:
                if token not in unknown:
                    unknown.append(token)
            elif code not in codes:
                codes.append(code)
        return ResolvedTerms(codes=codes, unknown=unknown)

    def leaf_states(
        self,
        included: Sequence[str],
        excluded: Sequence[str],
    ) -> dict[str, TriState]:
        """Push each selection down to the species the census holds.

        A clade code never appears in the census, so it takes its state to its
        leaves. An explicit leaf overrides the clade above it.
        """
        excluded_codes = set(excluded)
        included_codes = set(included)
        states: dict[str, TriState] = {}

        def walk(node: PhyleticNode, inherited: TriState | None) -> None:
            own: TriState | None = inherited
            if node.code in excluded_codes:
                own = "exclude"
            if node.code in included_codes:
                own = "include"
            if not node.children:
                if own is not None:
                    states[node.code] = own
                return
            for child in node.children:
                walk(child, own)

        for root in self.roots:
            walk(root, None)
        return states


def _split_proposal(proposal: str | list[str]) -> list[str]:
    """Split a proposal into trimmed terms, dropping blanks and the empty marker."""
    entries = [proposal] if isinstance(proposal, str) else proposal
    return [
        text
        for entry in entries
        for part in entry.split(",")
        if (text := part.strip()) and text.casefold() != NO_SPECIES
    ]


def encode_profile_pattern(states: Mapping[str, TriState]) -> str:
    """Write the census pattern for a set of species states.

    The census lists codes ascending and ``%A%B%`` means "A, then later B", so
    tokens out of that order describe a census that cannot exist. The empty
    selection is the bare wildcard, because WDK refuses an empty value.
    """
    tokens = sorted(
        f"{code}:{'Y' if state == 'include' else 'N'}" for code, state in states.items()
    )
    return f"%{'%'.join(tokens)}%" if tokens else NO_CONSTRAINT_PATTERN


def _join_codes(codes: Sequence[str]) -> str:
    kept = list(dict.fromkeys(code for code in codes if code))
    return ", ".join(kept) if kept else NO_SPECIES


def species_lists(
    included: Sequence[str],
    excluded: Sequence[str],
) -> tuple[str, str]:
    """The two documentation strings: each list of codes joined in the given
    order, or the empty marker when the list is empty."""
    return _join_codes(included), _join_codes(excluded)


def derive_binding(
    tree: PhyleticTree,
    included: str | list[str],
    excluded: str | list[str],
) -> PhyleticBinding | PhyleticUnresolved:
    """Turn two proposals into the three parameter values.

    Reports the reasons instead of a binding when a term is unknown or a code is
    in both proposals, because a code the vocabulary does not carry matches
    nothing and reports no error.
    """
    resolved_included = tree.resolve_terms(included)
    resolved_excluded = tree.resolve_terms(excluded)
    excluded_codes = set(resolved_excluded.codes)
    conflicts = [code for code in resolved_included.codes if code in excluded_codes]
    if resolved_included.unknown or resolved_excluded.unknown or conflicts:
        return PhyleticUnresolved(
            included_unknown=resolved_included.unknown,
            excluded_unknown=resolved_excluded.unknown,
            conflicts=conflicts,
        )
    included_list, excluded_list = species_lists(
        resolved_included.codes, resolved_excluded.codes
    )
    return PhyleticBinding(
        profile_pattern=encode_profile_pattern(
            tree.leaf_states(resolved_included.codes, resolved_excluded.codes)
        ),
        included_species=included_list,
        excluded_species=excluded_list,
    )

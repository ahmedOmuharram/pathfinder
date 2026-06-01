"""Pure WDK-mirroring value objects + typed walkers for parameter vocabularies.

These model the real shapes WDK returns (verified against wdk-client +
live API): standard-enum vocabularies (``[term, display, null]`` triples),
treeBox vocabulary trees, filter ontologies, and dataset parsers. They live
in the domain layer so both the integration parser (``wdk_parameters``) and
the transport DTOs can reference them without crossing layer boundaries.

The walkers (``flatten_vocab``, ``collect_leaf_terms``, ``find_vocab_node``,
``vocab_keys``) operate strictly on the typed union — no dict/list isinstance
dispatch, no raw-JSON access.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import Field, RootModel

from pathfinder.platform.pydantic_base import CamelModel


class WDKVocabNodeData(CamelModel):
    """The ``data`` payload of a treeBox vocabulary node."""

    term: str = ""
    display: str = ""


class WDKTreeBoxVocabNode(CamelModel):
    """A node in a treeBox enum vocabulary tree."""

    data: WDKVocabNodeData = Field(default_factory=WDKVocabNodeData)
    children: list[WDKTreeBoxVocabNode] = Field(default_factory=list)


class WDKVocabTerm(RootModel[tuple[str, str, None]]):
    """A standard-enum vocabulary entry: ``[term, display, null]``."""

    @property
    def term(self) -> str:
        return self.root[0]

    @property
    def display(self) -> str:
        return self.root[1]


class WDKFilterOntologyTerm(CamelModel):
    """A node in a filter parameter's ontology tree."""

    term: str
    parent: str | None = None
    display: str = ""
    description: str | None = None
    type: Literal["date", "string", "number", "multiFilter"] | None = None
    precision: int = 1
    is_range: bool = False


class WDKDatasetParser(CamelModel):
    """An input parser offered by a dataset parameter."""

    name: str
    display_name: str = ""
    description: str = ""


WDKVocabulary = list[WDKVocabTerm] | WDKTreeBoxVocabNode
"""Standard enum vocab (list of triples) or treeBox vocab (recursive tree)."""


class VocabOption(CamelModel):
    """A flattened vocabulary entry: the WDK-submittable term plus its label."""

    value: str
    display: str


def normalize_vocab_key(value: str) -> str:
    """Lowercase + collapse whitespace for tolerant vocabulary matching."""
    return re.sub(r"\s+", " ", value.strip()).lower()


def _walk_tree(node: WDKTreeBoxVocabNode) -> list[VocabOption]:
    options = [
        VocabOption(value=node.data.term, display=node.data.display or node.data.term)
    ]
    for child in node.children:
        options.extend(_walk_tree(child))
    return options


def flatten_vocab(vocab: WDKVocabulary | None) -> list[VocabOption]:
    """Flatten any vocabulary to ``VocabOption`` entries (tree walked DFS).

    For treeBox vocabularies this emits every node (parents and leaves); WDK
    accepts only leaves but PathFinder expands parents at submission time.
    """
    if vocab is None:
        return []
    if isinstance(vocab, WDKTreeBoxVocabNode):
        return [opt for opt in _walk_tree(vocab) if opt.value]
    return [VocabOption(value=t.term, display=t.display or t.term) for t in vocab]


def collect_leaf_terms(node: WDKTreeBoxVocabNode) -> list[str]:
    """Collect every leaf term under *node* (inclusive of leaf *node* itself)."""
    if not node.children:
        return [node.data.term] if node.data.term else []
    leaves: list[str] = []
    for child in node.children:
        leaves.extend(collect_leaf_terms(child))
    return leaves


def find_vocab_node(
    vocab: WDKVocabulary | None,
    match: str,
    *,
    normalize: bool = False,
) -> WDKTreeBoxVocabNode | None:
    """Find the treeBox node whose term or display equals *match* (DFS).

    List vocabularies have no tree structure and always return ``None``.
    """
    if not isinstance(vocab, WDKTreeBoxVocabNode) or not match:
        return None
    norm_match = normalize_vocab_key(match) if normalize else None

    def walk(node: WDKTreeBoxVocabNode) -> WDKTreeBoxVocabNode | None:
        candidates = [node.data.term, node.data.display]
        if match in candidates:
            return node
        if norm_match is not None and any(
            normalize_vocab_key(c) == norm_match for c in candidates if c
        ):
            return node
        for child in node.children:
            found = walk(child)
            if found is not None:
                return found
        return None

    return walk(vocab)


def vocab_keys(vocab: WDKVocabulary | None) -> set[str]:
    """All WDK-submittable terms: leaf terms for a tree, every term for a list."""
    if vocab is None:
        return set()
    if isinstance(vocab, WDKTreeBoxVocabNode):
        return {t for t in collect_leaf_terms(vocab) if t}
    return {t.term for t in vocab}

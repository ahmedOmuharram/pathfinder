from __future__ import annotations

from pathfinder.integrations.embeddings.prefixes import (
    SEARCH_DOCUMENT_PREFIX,
    SEARCH_QUERY_PREFIX,
)


def test_nomic_prefix_values_are_exact() -> None:
    """nomic-embed-text-v1.5 is trained on these literal task prefixes.

    Drift (plural, spacing, casing) silently degrades every retrieval path
    that shares them, so the contract is pinned here.
    """
    assert SEARCH_QUERY_PREFIX == "search_query: "
    assert SEARCH_DOCUMENT_PREFIX == "search_document: "

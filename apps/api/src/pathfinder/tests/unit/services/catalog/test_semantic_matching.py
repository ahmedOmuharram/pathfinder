"""The semantic bonus boosts a keyword candidate and never blocks the loop.

``SemanticSearchIndex.query`` runs a sentence-transformer, which holds the CPU
for hundreds of milliseconds. On the event loop that stalls every other request
served by the same worker, so the call belongs on a thread.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import cast

import pytest

from pathfinder.integrations.embeddings.semantic_index import SemanticSearchIndex
from pathfinder.integrations.veupathdb.discovery_service import DiscoveryService
from pathfinder.services.catalog import semantic_matching
from pathfinder.services.catalog.models import SearchMatch

SemanticHit = tuple[str, str, float]


@dataclass
class _StubIndex(SemanticSearchIndex):
    """An index that answers from a fixed list and records who called it."""

    hits: list[SemanticHit] = field(default_factory=list)
    callers: list[threading.Thread] = field(default_factory=list)

    def query(self, query_text: str, top_k: int = 20) -> list[SemanticHit]:
        del query_text, top_k
        self.callers.append(threading.current_thread())
        return list(self.hits)


class _FakeCatalog:
    def __init__(self, index: SemanticSearchIndex) -> None:
        self._index = index

    def get_semantic_index(self) -> SemanticSearchIndex:
        return self._index

    def find_search(self, record_type: str, search_name: str) -> None:
        """No catalog entry, so an injected search is skipped."""
        del record_type, search_name


class _FakeDiscovery:
    def __init__(self, catalog: _FakeCatalog) -> None:
        self._catalog = catalog

    async def get_catalog(self, site_id: str) -> _FakeCatalog:
        del site_id
        return self._catalog


def _match(name: str) -> SearchMatch:
    return SearchMatch(
        name=name, display_name=name, description="", record_type="transcript"
    )


def _discovery(index: SemanticSearchIndex) -> DiscoveryService:
    return cast("DiscoveryService", _FakeDiscovery(_FakeCatalog(index)))


@pytest.mark.asyncio
async def test_semantic_query_runs_off_event_loop() -> None:
    index = _StubIndex()

    await semantic_matching.apply_semantic_bonus(
        [(1.0, _match("GenesByText"))],
        _discovery(index),
        "plasmodb",
        "q",
        ["transcript"],
    )

    assert index.callers, "the index was never queried"
    assert index.callers[0] is not threading.main_thread(), (
        "the sentence-transformer ran on the event loop and stalls every other "
        "request the worker is serving"
    )


@pytest.mark.asyncio
async def test_a_similar_search_is_boosted_by_its_cosine() -> None:
    index = _StubIndex(hits=[("GenesByGoTerm", "transcript", 0.5)])
    scored = [(1.0, _match("GenesByGoTerm")), (2.0, _match("GenesByText"))]

    await semantic_matching.apply_semantic_bonus(
        scored, _discovery(index), "plasmodb", "kinase", ["transcript"]
    )

    assert scored[0][0] == pytest.approx(1.0 + 15.0 * 0.5)
    assert scored[1][0] == pytest.approx(2.0), "an unmatched search keeps its score"


@pytest.mark.asyncio
async def test_a_hit_from_another_record_type_is_not_boosted() -> None:
    index = _StubIndex(hits=[("GenesByGoTerm", "genomic-sequence", 0.9)])
    scored = [(1.0, _match("GenesByGoTerm"))]

    await semantic_matching.apply_semantic_bonus(
        scored, _discovery(index), "plasmodb", "kinase", ["transcript"]
    )

    assert scored[0][0] == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_an_empty_query_reads_no_index() -> None:
    index = _StubIndex(hits=[("GenesByGoTerm", "transcript", 0.9)])
    scored = [(1.0, _match("GenesByGoTerm"))]

    await semantic_matching.apply_semantic_bonus(
        scored, _discovery(index), "plasmodb", "", ["transcript"]
    )

    assert index.callers == []
    assert scored[0][0] == pytest.approx(1.0)

from __future__ import annotations

import threading
from typing import cast

import pytest

from pathfinder.integrations.embeddings.semantic_index import SemanticSearchIndex
from pathfinder.integrations.veupathdb.discovery_service import DiscoveryService
from pathfinder.services.catalog import semantic_matching


class _FakeCatalog:
    def __init__(self, index: SemanticSearchIndex) -> None:
        self._index = index

    def get_semantic_index(self) -> SemanticSearchIndex:
        return self._index

    def find_search(self, rt: str, name: str) -> None:
        return None


class _FakeDiscovery:
    def __init__(self, catalog: _FakeCatalog) -> None:
        self._catalog = catalog

    async def get_catalog(self, site_id: str) -> _FakeCatalog:
        return self._catalog


async def test_semantic_query_runs_off_event_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loop_thread = threading.current_thread()
    recorded: dict[str, threading.Thread] = {}

    index = SemanticSearchIndex()

    def fake_query(query_text: str, top_k: int = 20) -> list[tuple[str, str, float]]:
        recorded["thread"] = threading.current_thread()
        return []

    monkeypatch.setattr(index, "query", fake_query)
    discovery = _FakeDiscovery(_FakeCatalog(index))

    await semantic_matching.apply_semantic_bonus(
        scored=[],
        discovery=cast("DiscoveryService", discovery),
        site_id="plasmodb",
        query="kinase",
        record_types=["transcript"],
    )

    assert recorded["thread"] is not loop_thread

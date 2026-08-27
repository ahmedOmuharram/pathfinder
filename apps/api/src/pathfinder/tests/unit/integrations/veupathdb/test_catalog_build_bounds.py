"""What one process pays to build a site catalog, and how many it builds at once.

A cold build fetches the whole catalog and encodes the site's semantic index.
Concurrent builds sum, so a process that starts one per site exceeds any
ceiling. A held catalog also has to state its size for the eviction budget.
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from pathfinder.integrations.embeddings.semantic_index import SemanticSearchIndex
from pathfinder.integrations.veupathdb import discovery
from pathfinder.integrations.veupathdb.catalog_metadata import (
    DatasetMetadata,
    OntologyCategories,
)
from pathfinder.integrations.veupathdb.discovery import SearchCatalog
from pathfinder.integrations.veupathdb.disk_cache import (
    CatalogSnapshot,
    save_catalog_cache,
    try_load_catalog_cache,
)
from pathfinder.integrations.veupathdb.wdk_models import WDKRecordType, WDKSearch
from pathfinder.platform.config import get_settings


class _StubClient:
    """A client whose record-type read blocks until the test releases it."""

    def __init__(self, gate: asyncio.Event | None = None) -> None:
        self.gate = gate

    async def get_record_types(self, *, expanded: bool) -> list[WDKRecordType]:
        del expanded
        if self.gate is not None:
            await self.gate.wait()
        return []


@pytest.fixture
def offline_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cut the WDK reads and the disk write out of ``_fetch_from_api``."""

    async def _datasets(*_args: object) -> DatasetMetadata:
        return DatasetMetadata({}, {})

    async def _ontology(*_args: object) -> OntologyCategories:
        return OntologyCategories({}, set(), {})

    monkeypatch.setattr(discovery, "load_dataset_metadata", _datasets)
    monkeypatch.setattr(discovery, "load_ontology_categories", _ontology)
    monkeypatch.setattr(discovery, "save_catalog_cache", lambda *_a: None)


async def test_only_one_catalog_is_built_at_a_time(
    offline_fetch: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    del offline_fetch
    inflight = 0
    peak = 0

    async def counting_build(self: SearchCatalog) -> None:
        nonlocal inflight, peak
        del self
        inflight += 1
        peak = max(peak, inflight)
        await asyncio.sleep(0)
        inflight -= 1

    monkeypatch.setattr(SearchCatalog, "_build_semantic_index", counting_build)

    await asyncio.gather(
        SearchCatalog("a")._fetch_from_api(_StubClient()),
        SearchCatalog("b")._fetch_from_api(_StubClient()),
        SearchCatalog("c")._fetch_from_api(_StubClient()),
    )

    assert peak == 1


async def test_a_catalog_reports_the_bytes_it_holds(tmp_path: Path) -> None:
    catalog = SearchCatalog("testdb")
    snapshot = CatalogSnapshot(
        record_types=[],
        searches={"transcript": [WDKSearch(url_segment="A", display_name="A")]},
        dataset_summaries={},
        dataset_contacts={},
        search_categories={},
        available_categories=[],
    )
    save_catalog_cache("testdb", snapshot, cache_dir=tmp_path)
    restored = try_load_catalog_cache("testdb", cache_dir=tmp_path)
    assert restored is not None

    catalog._restore_from_snapshot(restored)
    index = SemanticSearchIndex(site_id="testdb")
    index.embeddings = np.zeros((4, 512), dtype=np.float32)
    catalog._semantic_index = index

    assert restored.payload_bytes == (tmp_path / "testdb.json").stat().st_size
    assert catalog.memory_bytes > restored.payload_bytes + index.embeddings.nbytes


async def test_an_unloaded_catalog_reports_a_size() -> None:
    assert SearchCatalog("testdb").memory_bytes > 0


def _stale_snapshot() -> CatalogSnapshot:
    return CatalogSnapshot(
        cached_at=0.0,
        record_types=[],
        searches={},
        dataset_summaries={},
        dataset_contacts={},
        search_categories={},
        available_categories=[],
    )


@pytest.fixture
def stale_cache(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """A stale snapshot on every load, and a record of what was spawned."""
    spawned: list[str] = []

    def _spawn(coro: Coroutine[Any, Any, None], *, name: str = "") -> None:
        coro.close()
        spawned.append(name)

    monkeypatch.setattr(
        discovery, "try_load_catalog_cache", lambda _s: _stale_snapshot()
    )
    monkeypatch.setattr(discovery, "spawn", _spawn)
    return spawned


async def test_a_refreshing_process_refreshes_a_stale_snapshot(
    stale_cache: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CATALOG_REFRESH_ENABLED", "true")
    get_settings.cache_clear()

    await SearchCatalog("testdb").load(_StubClient())
    get_settings.cache_clear()

    assert stale_cache == ["catalog-refresh-testdb"]


async def test_a_serving_process_keeps_the_stale_snapshot_and_builds_nothing(
    stale_cache: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A build inside a served call is what exceeds the 2g ceiling."""
    monkeypatch.setenv("CATALOG_REFRESH_ENABLED", "false")
    get_settings.cache_clear()

    await SearchCatalog("testdb").load(_StubClient())
    get_settings.cache_clear()

    assert stale_cache == []

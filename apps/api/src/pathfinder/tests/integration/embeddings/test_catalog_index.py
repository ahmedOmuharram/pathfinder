"""The site catalog's index over the shared record manager."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from assistant_core.embeddings.fake import FakeEmbedder
from assistant_core.embeddings.record_manager import index_size

from pathfinder.integrations.embeddings.semantic_index import (
    SemanticSearchIndex,
    catalog_index_id,
    enriched_text_limit,
)
from pathfinder.integrations.veupathdb.discovery import SearchCatalog
from pathfinder.integrations.veupathdb.wdk_models import WDKSearch
from pathfinder.platform.config import get_settings

pytestmark = pytest.mark.asyncio


def _search(name: str, display: str, description: str = "") -> WDKSearch:
    return WDKSearch(
        url_segment=name,
        display_name=display,
        description=description,
    )


_SEARCHES = {
    "transcript": [
        _search("GenesByGoTerm", "Genes by GO term", "gene ontology annotation"),
        _search("GenesByText", "Genes by text search", "free text over gene records"),
    ],
    "genomic-sequence": [_search("SequencesByLength", "Sequences by length")],
}


@pytest.fixture
def db(
    patch_app_db_engine: None,
    db_cleaner: None,
    embedding_index_cleaner: None,
) -> None:
    del patch_app_db_engine, db_cleaner, embedding_index_cleaner


async def test_a_build_syncs_one_entry_per_search(db: None) -> None:
    del db
    index = SemanticSearchIndex(site_id="testdb")
    report = await index.build(_SEARCHES)
    assert report.added == 3
    assert report.embedded_texts == 3
    assert await index_size(catalog_index_id("testdb")) == 3


async def test_a_second_build_of_the_same_catalog_embeds_nothing(
    db: None,
    fake_embedder: FakeEmbedder,
) -> None:
    del db
    await SemanticSearchIndex(site_id="testdb").build(_SEARCHES)
    fake_embedder.calls.clear()
    report = await SemanticSearchIndex(site_id="testdb").build(_SEARCHES)
    assert report.reused == 3
    assert report.embedded_texts == 0
    assert fake_embedder.calls == []


async def test_a_build_that_may_not_sync_writes_nothing(
    db: None,
    fake_embedder: FakeEmbedder,
) -> None:
    del db
    index = SemanticSearchIndex(site_id="testdb")
    report = await index.build(_SEARCHES, sync=False)
    assert report.added == 0
    assert len(index.entries) == 3
    assert fake_embedder.calls == []
    assert await index_size(catalog_index_id("testdb")) == 0


async def test_a_query_answers_with_the_search_and_its_record_type(db: None) -> None:
    del db
    index = SemanticSearchIndex(site_id="testdb")
    await index.build(_SEARCHES)
    wanted = next(e for e in index.entries if e.search_name == "GenesByGoTerm")
    hits = await index.query(wanted.enriched_text, top_k=3)
    assert hits[0][0] == "GenesByGoTerm"
    assert hits[0][1] == "transcript"
    assert hits[0][2] == pytest.approx(1.0, abs=1e-6)
    assert {name for name, _, _ in hits} == {
        "GenesByGoTerm",
        "GenesByText",
        "SequencesByLength",
    }


async def test_a_query_on_another_site_reads_nothing(db: None) -> None:
    del db
    await SemanticSearchIndex(site_id="testdb").build(_SEARCHES)
    assert await SemanticSearchIndex(site_id="otherdb").query("anything") == []


async def test_the_enriched_text_is_cut_at_the_bound(db: None) -> None:
    del db
    index = SemanticSearchIndex(site_id="testdb")
    await index.build(
        {"transcript": [_search("Long", "Long search", "d" * 9000)]},
        sync=False,
    )
    assert len(index.entries[0].enriched_text) == enriched_text_limit()


async def test_an_empty_catalog_syncs_nothing(db: None) -> None:
    del db
    index = SemanticSearchIndex(site_id="testdb")
    report = await index.build({})
    assert report.added == 0
    assert index.entries == []


@pytest.fixture
def sync_disabled(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("EMBEDDING_INDEX_SYNC_ENABLED", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def test_a_catalog_build_that_may_not_sync_writes_no_vector(
    db: None,
    sync_disabled: None,
    fake_embedder: FakeEmbedder,
) -> None:
    """The gate lives on the catalog build, not only on the adapter."""
    del db, sync_disabled
    catalog = SearchCatalog("gateddb")
    catalog._searches = _SEARCHES

    await catalog._build_semantic_index()

    assert await index_size(catalog_index_id("gateddb")) == 0
    assert fake_embedder.calls == []
    index = catalog.get_semantic_index()
    assert index is not None
    assert len(index.entries) == 3


async def test_a_catalog_build_that_may_sync_writes_its_vectors(
    db: None,
    fake_embedder: FakeEmbedder,
) -> None:
    del db
    catalog = SearchCatalog("openeddb")
    catalog._searches = _SEARCHES

    await catalog._build_semantic_index()

    assert await index_size(catalog_index_id("openeddb")) == 3
    assert fake_embedder.calls != []

"""The embedding cache stores one row per entry, keyed by that entry's text."""

from __future__ import annotations

import asyncio
import hashlib
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from numpy.typing import NDArray

from pathfinder.integrations.embeddings import semantic_index
from pathfinder.integrations.embeddings.prefixes import SEARCH_DOCUMENT_PREFIX
from pathfinder.integrations.embeddings.semantic_index import (
    SemanticSearchIndex,
    set_cache_dir,
)
from pathfinder.integrations.veupathdb.wdk_models import WDKSearch


def _vector_for(text: str, width: int) -> NDArray[Any]:
    """Return the deterministic vector a fake model gives one text."""
    seed = int(hashlib.sha256(text.encode()).hexdigest()[:8], 16) % 997
    return np.full(width, float(seed), dtype=np.float32)


class _CountingModel:
    """Embeds deterministic vectors and records the texts of every batch."""

    def __init__(self, width: int = 8) -> None:
        self.width = width
        self.batches: list[list[str]] = []

    def embed(self, texts: list[str], batch_size: int = 8) -> Iterator[NDArray[Any]]:
        del batch_size
        self.batches.append(list(texts))
        for text in texts:
            yield _vector_for(text, self.width)


class _BlockingModel:
    """Blocks inside ``embed`` until the caller releases it."""

    def __init__(self, width: int = 8) -> None:
        self.width = width
        self.entered = threading.Event()
        self.release = threading.Event()
        self.released = False

    def embed(self, texts: list[str], batch_size: int = 8) -> Iterator[NDArray[Any]]:
        del batch_size
        self.entered.set()
        self.released = self.release.wait(timeout=5.0)
        for text in texts:
            yield _vector_for(text, self.width)


@pytest.fixture
def model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _CountingModel:
    set_cache_dir(tmp_path)
    counting = _CountingModel()
    monkeypatch.setattr(semantic_index, "get_embedding_model", lambda: counting)
    return counting


def _search(name: str) -> WDKSearch:
    return WDKSearch(url_segment=name, display_name=name, description=f"{name} desc")


def _file_names(directory: Path) -> list[str]:
    """The names in a directory, read outside the event loop's coroutines."""
    return sorted(p.name for p in directory.iterdir())


def _documents(index: SemanticSearchIndex, *names: str) -> list[str]:
    """The prefixed texts the model must receive for the named searches."""
    return [
        f"{SEARCH_DOCUMENT_PREFIX}{e.enriched_text}"
        for e in index.entries
        if not names or e.search_name in names
    ]


async def test_the_cache_survives_a_reordered_catalog(model: _CountingModel) -> None:
    by_rt_one = {
        "transcript": [_search("GenesByText")],
        "dataset": [_search("DatasetsByText")],
    }
    by_rt_two = {
        "dataset": [_search("DatasetsByText")],
        "transcript": [_search("GenesByText")],
    }

    first = SemanticSearchIndex(site_id="testdb")
    await first.build(by_rt_one)
    second = SemanticSearchIndex(site_id="testdb")
    await second.build(by_rt_two)

    assert len(model.batches) == 1
    assert second.embeddings is not None


async def test_entries_are_canonically_ordered_so_rows_align(
    model: _CountingModel,
) -> None:
    del model
    by_rt_one = {
        "transcript": [_search("B"), _search("A")],
        "dataset": [_search("C")],
    }
    by_rt_two = {
        "dataset": [_search("C")],
        "transcript": [_search("A"), _search("B")],
    }

    first = SemanticSearchIndex(site_id="testdb")
    await first.build(by_rt_one)
    second = SemanticSearchIndex(site_id="testdb")
    await second.build(by_rt_two)

    assert [(e.record_type, e.search_name) for e in first.entries] == [
        (e.record_type, e.search_name) for e in second.entries
    ]


async def test_only_a_new_entry_is_embedded(model: _CountingModel) -> None:
    first = SemanticSearchIndex(site_id="testdb")
    await first.build({"transcript": [_search("A"), _search("B")]})

    second = SemanticSearchIndex(site_id="testdb")
    await second.build({"transcript": [_search("A"), _search("B"), _search("C")]})

    assert model.batches[-1] == _documents(second, "C")
    assert second.embeddings is not None
    assert np.array_equal(
        second.embeddings,
        np.array([_vector_for(t, model.width) for t in _documents(second)]),
    )


async def test_a_removed_entry_drops_its_key_and_keeps_the_others(
    model: _CountingModel, tmp_path: Path
) -> None:
    first = SemanticSearchIndex(site_id="testdb")
    await first.build({"transcript": [_search("A"), _search("B"), _search("C")]})

    second = SemanticSearchIndex(site_id="testdb")
    await second.build({"transcript": [_search("A"), _search("C")]})

    assert len(model.batches) == 1
    stored = np.load(tmp_path / "testdb.npz")
    assert [str(k) for k in stored["keys"]] == [e.cache_key for e in second.entries]
    assert stored["embeddings"].shape[0] == 2
    assert _file_names(tmp_path) == ["testdb.npz"]


async def test_an_old_format_cache_file_is_a_miss(
    model: _CountingModel, tmp_path: Path
) -> None:
    path = tmp_path / "testdb.npz"
    np.savez_compressed(
        path, embeddings=np.zeros((2, 8)), hash=np.array("0123456789abcdef")
    )

    index = SemanticSearchIndex(site_id="testdb")
    await index.build({"transcript": [_search("A"), _search("B")]})

    assert model.batches == [_documents(index)]
    stored = np.load(path)
    assert [str(k) for k in stored["keys"]] == [e.cache_key for e in index.entries]


async def test_a_truncated_cache_file_is_a_miss(
    model: _CountingModel, tmp_path: Path
) -> None:
    path = tmp_path / "testdb.npz"
    path.write_bytes(b"PK\x03\x04 truncated")

    index = SemanticSearchIndex(site_id="testdb")
    await index.build({"transcript": [_search("A")]})

    assert model.batches == [_documents(index)]
    stored = np.load(path)
    assert [str(k) for k in stored["keys"]] == [e.cache_key for e in index.entries]


async def test_a_model_width_change_is_a_miss(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    set_cache_dir(tmp_path)
    narrow = _CountingModel(width=4)
    monkeypatch.setattr(semantic_index, "get_embedding_model", lambda: narrow)
    first = SemanticSearchIndex(site_id="testdb")
    await first.build({"transcript": [_search("A"), _search("B")]})

    wide = _CountingModel(width=8)
    monkeypatch.setattr(semantic_index, "get_embedding_model", lambda: wide)
    second = SemanticSearchIndex(site_id="testdb")
    await second.build({"transcript": [_search("A"), _search("B"), _search("C")]})

    assert wide.batches[-1] == _documents(second)
    assert second.embeddings is not None
    assert second.embeddings.shape == (3, 8)


async def test_the_embed_leaves_the_event_loop_free(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    set_cache_dir(tmp_path)
    blocking = _BlockingModel()
    monkeypatch.setattr(semantic_index, "get_embedding_model", lambda: blocking)

    index = SemanticSearchIndex(site_id="testdb")
    build = asyncio.create_task(index.build({"transcript": [_search("A")]}))

    for _ in range(2000):
        if blocking.entered.is_set():
            break
        await asyncio.sleep(0.001)
    assert blocking.entered.is_set()

    ticks = 0
    for _ in range(3):
        await asyncio.sleep(0.001)
        ticks += 1
    blocking.release.set()
    await build

    assert blocking.released
    assert ticks == 3
    assert index.embeddings is not None

"""Semantic search index over enriched WDK search descriptions.

Embeddings are cached to disk per site, one row per entry keyed by the content
that produced it, so a catalog change re-encodes only the entries that changed.
"""

from __future__ import annotations

import asyncio
import gc
import hashlib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from zipfile import BadZipFile

import numpy as np
from assistant_core.embeddings.model import MODEL_NAME, get_embedding_model
from assistant_core.embeddings.prefixes import (
    SEARCH_DOCUMENT_PREFIX,
    SEARCH_QUERY_PREFIX,
)
from assistant_core.platform.logging import get_logger
from numpy.typing import NDArray

from pathfinder.integrations.veupathdb.wdk_models import WDKSearch

logger = get_logger(__name__)

_STORE_NDIM = 2

# Pre-computed embeddings shipped with the repo.
_BUNDLED_CACHE_DIR = (
    Path(__file__).resolve().parent.parent.parent / "data" / "embeddings"
)


class _CacheConfig:
    """Holds the runtime cache directory."""

    dir: Path = _BUNDLED_CACHE_DIR


_cache_config = _CacheConfig()


def set_cache_dir(path: Path) -> None:
    """Set the runtime cache directory."""
    _cache_config.dir = path
    _cache_config.dir.mkdir(parents=True, exist_ok=True)


def _strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    return re.sub(r"<[^>]+>", " ", text)


def _format_param_names(param_names: list[str]) -> str:
    """Convert param names from snake_case to readable words."""
    if not param_names:
        return ""
    return " ".join(name.replace("_", " ") for name in param_names)


def _cache_path(cache_dir: Path, site_id: str) -> Path:
    """Path to the cached embeddings file for a site."""
    return cache_dir / f"{site_id}.npz"


def _load_cached_rows(site_id: str) -> dict[str, NDArray[Any]]:
    """Map cache key to stored row, reading the runtime then the bundled file.

    A file without a ``keys`` array, or with rows of a second width, is ignored.
    """
    rows: dict[str, NDArray[Any]] = {}
    width: int | None = None
    for cache_dir in dict.fromkeys((_cache_config.dir, _BUNDLED_CACHE_DIR)):
        path = _cache_path(cache_dir, site_id)
        if not path.exists():
            continue
        try:
            with np.load(path) as data:
                if "keys" not in data or "embeddings" not in data:
                    continue
                keys = data["keys"]
                embeddings: NDArray[Any] = data["embeddings"]
            if embeddings.ndim != _STORE_NDIM or len(keys) != embeddings.shape[0]:
                continue
            if width is None:
                width = int(embeddings.shape[1])
            if int(embeddings.shape[1]) != width:
                continue
            for i, key in enumerate(keys):
                rows.setdefault(str(key), embeddings[i])
        except OSError, ValueError, KeyError, BadZipFile:
            logger.debug("Cache load failed", path=str(path))
    return rows


def _save_cache(site_id: str, rows: dict[str, NDArray[Any]]) -> None:
    """Replace the site's cache file with exactly the given rows."""
    _cache_config.dir.mkdir(parents=True, exist_ok=True)
    path = _cache_path(_cache_config.dir, site_id)
    # Processes share the cache directory, so a reader never sees a partial file.
    staged = path.with_name(f"{path.stem}.{os.getpid()}.staged.npz")
    try:
        np.savez_compressed(
            staged,
            keys=np.array(list(rows)),
            embeddings=np.array(list(rows.values())),
        )
        staged.replace(path)
    except OSError:
        logger.warning("Failed to save embedding cache", path=str(path), exc_info=True)
        staged.unlink(missing_ok=True)


def _embed(texts: list[str]) -> list[NDArray[Any]]:
    """Encode texts with the fastembed model."""
    model = get_embedding_model()
    rows = list(model.embed(texts, batch_size=8))
    gc.collect()
    return rows


async def _encode(entries: list[SearchIndexEntry]) -> list[NDArray[Any]]:
    """Encode entry texts in a worker thread so the event loop stays free."""
    if not entries:
        return []
    texts = [f"{SEARCH_DOCUMENT_PREFIX}{e.enriched_text}" for e in entries]
    return await asyncio.to_thread(_embed, texts)


@dataclass
class SearchIndexEntry:
    """A single entry in the semantic search index."""

    search_name: str
    record_type: str
    enriched_text: str

    @property
    def cache_key(self) -> str:
        """Content address of this entry's row.

        The model, the document prefix, and the text all decide the vector.
        """
        payload = "\n".join((MODEL_NAME, SEARCH_DOCUMENT_PREFIX, self.enriched_text))
        return hashlib.sha256(payload.encode()).hexdigest()


@dataclass
class SemanticSearchIndex:
    """Cosine-similarity index over enriched WDK search descriptions."""

    site_id: str = ""
    entries: list[SearchIndexEntry] = field(default_factory=list)
    embeddings: NDArray[Any] | None = None

    async def build(
        self,
        searches_by_rt: dict[str, list[WDKSearch]],
        category_labels: dict[str, str] | None = None,
    ) -> None:
        """Build the index from search catalog data.

        The model runs only for entries whose text has no cached row, and it
        runs in a worker thread so the event loop stays free.
        """
        cats = category_labels or {}
        self.entries = []

        for rt_name, searches in searches_by_rt.items():
            for s in searches:
                text = self._build_enriched_text(s, cats)
                self.entries.append(
                    SearchIndexEntry(
                        search_name=s.url_segment,
                        record_type=rt_name,
                        enriched_text=text,
                    )
                )

        if not self.entries:
            return

        # Canonical order: one catalog content gives one entry sequence and one
        # stored file, whatever order the fetch returned.
        self.entries.sort(key=lambda e: (e.record_type, e.search_name))

        cached = _load_cached_rows(self.site_id)
        stored_keys = set(cached)
        pending = [e for e in self.entries if e.cache_key not in cached]
        fresh = await _encode(pending)

        if fresh and cached:
            model_width = int(fresh[0].shape[0])
            cached_width = int(next(iter(cached.values())).shape[0])
            if model_width != cached_width:
                logger.info(
                    "Cached rows do not match the model width, re-encoding the site",
                    site_id=self.site_id,
                    cached_width=cached_width,
                    model_width=model_width,
                )
                cached = {}
                pending = list(self.entries)
                fresh = await _encode(pending)

        fresh_rows = iter(fresh)
        store: dict[str, NDArray[Any]] = {}
        rows: list[NDArray[Any]] = []
        for entry in self.entries:
            key = entry.cache_key
            row = cached[key] if key in cached else next(fresh_rows)
            rows.append(row)
            store[key] = row
        self.embeddings = np.array(rows)

        if pending or stored_keys != set(store):
            _save_cache(self.site_id, store)

        logger.info(
            "Semantic search index ready",
            site_id=self.site_id,
            num_entries=len(self.entries),
            encoded=len(pending),
            embedding_dim=int(self.embeddings.shape[1]),
        )

    def query(self, query_text: str, top_k: int = 20) -> list[tuple[str, str, float]]:
        """Find the top-k most similar searches.

        Returns list of (search_name, record_type, similarity_score).
        """
        if self.embeddings is None or not self.entries:
            return []

        model = get_embedding_model()
        query_emb = np.array(list(model.embed([f"{SEARCH_QUERY_PREFIX}{query_text}"])))
        similarities = (self.embeddings @ query_emb.T).flatten()

        top_indices = np.argsort(similarities)[::-1][:top_k]
        results = []
        for idx in top_indices:
            entry = self.entries[idx]
            score = float(similarities[idx])
            if score > 0.0:
                results.append((entry.search_name, entry.record_type, score))
        return results

    def _build_enriched_text(
        self,
        search: WDKSearch,
        category_labels: dict[str, str],
    ) -> str:
        """Build the enriched text for a search.

        The most discriminating signals come first.
        """
        parts: list[str] = []

        cat = category_labels.get(search.url_segment, "")
        if cat:
            parts.append(cat)

        parts.extend(
            " ".join(str(v) for v in prop_values)
            for prop_values in search.properties.values()
            if prop_values
        )

        parts.append(search.display_name)
        if (
            search.short_display_name
            and search.short_display_name != search.display_name
        ):
            parts.append(search.short_display_name)

        if search.summary:
            parts.append(search.summary)

        parts.extend(g.display_name for g in search.groups if g.display_name)

        param_text = _format_param_names(search.param_names)
        if param_text:
            parts.append(param_text)

        name_words = " ".join(
            re.findall(r"[A-Z][a-z]+|[a-z]+|[A-Z]+|\d+", search.url_segment)
        )
        parts.append(name_words)

        parts.append(_strip_html(search.description))

        for attr in search.dynamic_attributes:
            attr_name = attr.get("displayName", "") if hasattr(attr, "get") else ""
            if attr_name and attr_name != "Search Weight":
                parts.append(str(attr_name))

        return " ".join(p for p in parts if p).strip()

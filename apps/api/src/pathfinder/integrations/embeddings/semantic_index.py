"""Semantic search index over enriched WDK search descriptions.

Embeddings are cached to disk per site and are re-encoded only when the search
catalog changes.
"""

from __future__ import annotations

import gc
import hashlib
import json
import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from fastembed import TextEmbedding
from numpy.typing import NDArray

from pathfinder.integrations.embeddings.prefixes import (
    SEARCH_DOCUMENT_PREFIX,
    SEARCH_QUERY_PREFIX,
)
from pathfinder.integrations.veupathdb.wdk_models import WDKSearch
from pathfinder.platform.logging import get_logger

logger = get_logger(__name__)

_MODEL_NAME = "nomic-ai/nomic-embed-text-v1.5"

# Pre-computed embeddings shipped with the repo.
_BUNDLED_CACHE_DIR = (
    Path(__file__).resolve().parent.parent.parent / "data" / "embeddings"
)


class _CacheConfig:
    """Holds the runtime cache directory."""

    dir: Path = _BUNDLED_CACHE_DIR


_cache_config = _CacheConfig()


class _ModelState:
    """Thread-safe singleton holder for the fastembed model."""

    _instance: TextEmbedding | None = None
    _lock: threading.Lock = threading.Lock()

    @classmethod
    def get(cls) -> TextEmbedding:
        """Return the singleton model, loading it on first call."""
        if cls._instance is not None:
            return cls._instance
        with cls._lock:
            if cls._instance is not None:
                return cls._instance
            logger.info("Loading fastembed model", model=_MODEL_NAME)
            cache_dir = os.getenv("FASTEMBED_CACHE_DIR") or None
            cls._instance = TextEmbedding(model_name=_MODEL_NAME, cache_dir=cache_dir)
            logger.info("Fastembed model loaded")
            return cls._instance


def set_cache_dir(path: Path) -> None:
    """Set the runtime cache directory."""
    _cache_config.dir = path
    _cache_config.dir.mkdir(parents=True, exist_ok=True)


def get_embedding_model() -> TextEmbedding:
    """Return the lazy-loaded fastembed model singleton."""
    return _ModelState.get()


def warm_up_model() -> None:
    """Load the embedding model before the first request."""
    get_embedding_model()


def _strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    return re.sub(r"<[^>]+>", " ", text)


def _format_param_names(param_names: list[str]) -> str:
    """Convert param names from snake_case to readable words."""
    if not param_names:
        return ""
    return " ".join(name.replace("_", " ") for name in param_names)


def _catalog_hash(entries: list[SearchIndexEntry]) -> str:
    """Return a stable hash of the catalog entries."""
    key = json.dumps(
        [(e.search_name, e.record_type) for e in entries],
        sort_keys=True,
    )
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _cache_path(site_id: str) -> Path:
    """Path to the cached embeddings file for a site."""
    return _cache_config.dir / f"{site_id}.npz"


def _try_load_cache(site_id: str, catalog_hash: str) -> NDArray[Any] | None:
    """Load cached embeddings from the runtime or the bundled directory."""
    for cache_dir in (_cache_config.dir, _BUNDLED_CACHE_DIR):
        path = cache_dir / f"{site_id}.npz"
        if not path.exists():
            continue
        try:
            data = np.load(path)
            stored_hash = data.get("hash", None)
            if stored_hash is not None and str(stored_hash) == catalog_hash:
                result: NDArray[Any] = data["embeddings"]
                return result
        except OSError, ValueError, KeyError:
            logger.debug("Cache load failed", path=str(path))
    return None


def _save_cache(site_id: str, catalog_hash: str, embeddings: NDArray[Any]) -> None:
    """Save embeddings to the runtime cache directory."""
    _cache_config.dir.mkdir(parents=True, exist_ok=True)
    path = _cache_path(site_id)
    try:
        np.savez_compressed(path, embeddings=embeddings, hash=np.array(catalog_hash))
    except OSError:
        logger.warning("Failed to save embedding cache", path=str(path), exc_info=True)


@dataclass
class SearchIndexEntry:
    """A single entry in the semantic search index."""

    search_name: str
    record_type: str
    enriched_text: str


@dataclass
class SemanticSearchIndex:
    """Cosine-similarity index over enriched WDK search descriptions."""

    site_id: str = ""
    entries: list[SearchIndexEntry] = field(default_factory=list)
    embeddings: NDArray[Any] | None = None

    def build(
        self,
        searches_by_rt: dict[str, list[WDKSearch]],
        category_labels: dict[str, str] | None = None,
    ) -> None:
        """Build the index from search catalog data.

        The model runs only when the disk cache is missing or stale.
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

        h = _catalog_hash(self.entries)

        cached = _try_load_cache(self.site_id, h)
        if cached is not None and cached.shape[0] == len(self.entries):
            self.embeddings = cached
            logger.info(
                "Loaded embeddings from cache",
                site_id=self.site_id,
                num_entries=len(self.entries),
            )
            return

        model = get_embedding_model()
        texts = [f"{SEARCH_DOCUMENT_PREFIX}{e.enriched_text}" for e in self.entries]
        self.embeddings = np.array(list(model.embed(texts, batch_size=8)))
        _save_cache(self.site_id, h, self.embeddings)
        # Release the encoding intermediates before the next site.
        del texts
        gc.collect()
        logger.info(
            "Semantic search index built and cached",
            site_id=self.site_id,
            num_entries=len(self.entries),
            embedding_dim=self.embeddings.shape[1]
            if self.embeddings is not None
            else 0,
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

"""Semantic search index for WDK search discovery.

Uses fastembed (nomic-embed-text-v1.5, ONNX Runtime, 8192 context) to embed enriched
search descriptions.  Embeddings are cached to disk as .npz files keyed by a
hash of the search names — so startup loads from cache in milliseconds
and only re-embeds when the catalog actually changes.

Pre-computed caches are committed to the repo under
``data/embeddings/``.  At runtime, caches are read/written to a
configurable directory (default: same ``data/embeddings/``).
"""

from __future__ import annotations

import gc
import hashlib
import json
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from fastembed import TextEmbedding
from numpy.typing import NDArray

from pathfinder.integrations.veupathdb.wdk_models import WDKSearch
from pathfinder.platform.logging import get_logger

logger = get_logger(__name__)

_MODEL_NAME = "nomic-ai/nomic-embed-text-v1.5"

# Pre-computed embeddings shipped with the repo.
_BUNDLED_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "embeddings"


class _CacheConfig:
    """Mutable container for the runtime cache directory (avoids global reassignment)."""

    dir: Path = _BUNDLED_CACHE_DIR


_cache_config = _CacheConfig()


class _ModelState:
    """Thread-safe singleton container for the fastembed TextEmbedding model."""

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
            cls._instance = TextEmbedding(model_name=_MODEL_NAME)
            logger.info("Fastembed model loaded")
            return cls._instance


def set_cache_dir(path: Path) -> None:
    """Override the runtime cache directory used at runtime."""
    _cache_config.dir = path
    _cache_config.dir.mkdir(parents=True, exist_ok=True)


def _get_model() -> TextEmbedding:
    """Return the lazy-loaded fastembed model singleton."""
    return _ModelState.get()


def warm_up_model() -> None:
    """Eagerly load the embedding model so the first request doesn't pay for it."""
    _get_model()


def _strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    return re.sub(r"<[^>]+>", " ", text)


def _format_param_names(param_names: list[str]) -> str:
    """Convert param names from snake_case to readable words."""
    if not param_names:
        return ""
    return " ".join(name.replace("_", " ") for name in param_names)


def _catalog_hash(entries: list[SearchIndexEntry]) -> str:
    """Stable hash of search names — changes when the catalog changes."""
    key = json.dumps(
        [(e.search_name, e.record_type) for e in entries],
        sort_keys=True,
    )
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _cache_path(site_id: str) -> Path:
    """Path to the cached embeddings file for a site."""
    return _cache_config.dir / f"{site_id}.npz"


def _try_load_cache(
    site_id: str, catalog_hash: str
) -> NDArray[Any] | None:
    """Try loading cached embeddings, checking both runtime and bundled dirs."""
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
        except (OSError, ValueError, KeyError):
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
        dataset_summaries: dict[str, str] | None = None,
        dataset_contacts: dict[str, str] | None = None,
    ) -> None:
        """Build the index from search catalog data.

        Checks the disk cache first.  Only encodes with the model if
        the cache is missing or stale.
        """
        ds_summaries = dataset_summaries or {}
        ds_contacts = dataset_contacts or {}
        self.entries = []

        for rt_name, searches in searches_by_rt.items():
            for s in searches:
                text = self._build_enriched_text(s, ds_summaries, ds_contacts)
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

        # Try loading from cache.
        cached = _try_load_cache(self.site_id, h)
        if cached is not None and cached.shape[0] == len(self.entries):
            self.embeddings = cached
            logger.info(
                "Loaded embeddings from cache",
                site_id=self.site_id,
                num_entries=len(self.entries),
            )
            return

        # Cache miss — encode with fastembed.
        model = _get_model()
        texts = [f"search_document: {e.enriched_text}" for e in self.entries]
        self.embeddings = np.array(list(model.embed(texts, batch_size=8)))
        _save_cache(self.site_id, h, self.embeddings)
        # Free encoding intermediates before moving to the next site.
        del texts
        gc.collect()
        logger.info(
            "Semantic search index built and cached",
            site_id=self.site_id,
            num_entries=len(self.entries),
            embedding_dim=self.embeddings.shape[1] if self.embeddings is not None else 0,
        )

    def query(self, query_text: str, top_k: int = 20) -> list[tuple[str, str, float]]:
        """Find the top-k most similar searches.

        Returns list of (search_name, record_type, similarity_score).
        """
        if self.embeddings is None or not self.entries:
            return []

        model = _get_model()
        query_emb = np.array(list(model.embed([f"search_query: {query_text}"])))
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
        ds_summaries: dict[str, str],
        ds_contacts: dict[str, str],
    ) -> str:
        """Build enriched text blob for a search.

        Structures the text to front-load discriminating signals:
        1. Search properties (displayCategory, organisms — from WDK metadata)
        2. Display name + short display name
        3. Summary
        4. Parameter names (split from snake_case)
        5. CamelCase-split search name
        6. Description (HTML-stripped)
        7. Dataset summaries (by ID match in search name)
        """
        parts: list[str] = []

        # 1. All properties as readable text (displayCategory, organisms, etc.)
        parts.extend(
            " ".join(str(v) for v in prop_values)
            for prop_values in search.properties.values()
            if prop_values
        )

        # 2. Display names
        parts.append(search.display_name)
        short = getattr(search, "short_display_name", "")
        if short and short != search.display_name:
            parts.append(short)

        # 3. Summary
        summary = getattr(search, "summary", "")
        if summary:
            parts.append(summary)

        # 4. Parameter names (snake_case → readable words)
        param_text = _format_param_names(search.param_names)
        if param_text:
            parts.append(param_text)

        # 5. CamelCase-split search name
        name_words = " ".join(re.findall(r"[A-Z][a-z]+|[a-z]+|[A-Z]+|\d+", search.url_segment))
        parts.append(name_words)

        # 6. Description (HTML-stripped)
        parts.append(_strip_html(search.description))

        # 7. Dataset summaries by ID match
        for ds_id, ds_summary in ds_summaries.items():
            if ds_id in search.url_segment:
                parts.append(_strip_html(ds_summary))
                contact = ds_contacts.get(ds_id, "")
                if contact:
                    parts.append(contact)

        return " ".join(p for p in parts if p).strip()

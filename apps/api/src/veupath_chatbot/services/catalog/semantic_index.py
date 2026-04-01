"""Semantic search index for WDK search discovery.

Uses sentence-transformers (nomic-embed-text-v1.5, 8192 context) to embed enriched search
descriptions.  Embeddings are cached to disk as .npz files keyed by a
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

import numpy as np
from numpy.typing import NDArray

from veupath_chatbot.platform.logging import get_logger

logger = get_logger(__name__)

_MODEL_NAME = "nomic-ai/nomic-embed-text-v1.5"
_model_lock = threading.Lock()
_model_instance = None

# Pre-computed embeddings shipped with the repo.
_BUNDLED_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "embeddings"
# Runtime cache — defaults to bundled dir but can be overridden (e.g. Docker volume).
_RUNTIME_CACHE_DIR: Path = _BUNDLED_CACHE_DIR


def set_cache_dir(path: Path) -> None:
    """Override the runtime embedding cache directory."""
    global _RUNTIME_CACHE_DIR
    _RUNTIME_CACHE_DIR = path
    _RUNTIME_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _get_model():
    """Lazy-load the sentence-transformer model (thread-safe singleton)."""
    global _model_instance
    if _model_instance is not None:
        return _model_instance
    with _model_lock:
        if _model_instance is not None:
            return _model_instance
        from sentence_transformers import SentenceTransformer

        logger.info("Loading sentence-transformer model", model=_MODEL_NAME)
        _model_instance = SentenceTransformer(_MODEL_NAME, trust_remote_code=True)
        logger.info("Sentence-transformer model loaded")
        return _model_instance


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
    return _RUNTIME_CACHE_DIR / f"{site_id}.npz"


def _try_load_cache(
    site_id: str, catalog_hash: str
) -> NDArray | None:
    """Try loading cached embeddings, checking both runtime and bundled dirs."""
    for cache_dir in (_RUNTIME_CACHE_DIR, _BUNDLED_CACHE_DIR):
        path = cache_dir / f"{site_id}.npz"
        if not path.exists():
            continue
        try:
            data = np.load(path)
            if data.get("hash", None) is not None and str(data["hash"]) == catalog_hash:
                return data["embeddings"]
        except Exception:
            logger.debug("Cache load failed", path=str(path))
    return None


def _save_cache(site_id: str, catalog_hash: str, embeddings: NDArray) -> None:
    """Save embeddings to the runtime cache directory."""
    _RUNTIME_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(site_id)
    try:
        np.savez_compressed(path, embeddings=embeddings, hash=np.array(catalog_hash))
    except Exception:
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
    embeddings: NDArray | None = None

    def build(
        self,
        searches_by_rt: dict[str, list],
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

        # Cache miss — encode in small batches to limit peak memory.
        model = _get_model()
        texts = [f"search_document: {e.enriched_text}" for e in self.entries]
        self.embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False, batch_size=8)
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
        query_emb = model.encode([f"search_query: {query_text}"], normalize_embeddings=True)
        similarities = (self.embeddings @ query_emb.T).flatten()

        top_indices = np.argsort(similarities)[::-1][:top_k]
        results = []
        for idx in top_indices:
            entry = self.entries[idx]
            score = float(similarities[idx])
            if score > 0.0:
                results.append((entry.search_name, entry.record_type, score))
        return results

    def _build_enriched_text(self, search, ds_summaries: dict, ds_contacts: dict) -> str:
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
        for prop_values in search.properties.values():
            if prop_values:
                parts.append(" ".join(str(v) for v in prop_values))

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

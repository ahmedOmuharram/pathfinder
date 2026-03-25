"""Lightweight semantic search index for WDK search discovery.

Uses sentence-transformers (all-MiniLM-L6-v2) to embed enriched search
descriptions at catalog load time.  At query time, the user query is
embedded and compared via cosine similarity.

The index is built once per site and cached alongside the SearchCatalog.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from veupath_chatbot.platform.logging import get_logger

logger = get_logger(__name__)

_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_model_lock = threading.Lock()
_model_instance = None


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
        _model_instance = SentenceTransformer(_MODEL_NAME)
        logger.info("Sentence-transformer model loaded")
        return _model_instance


def _strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    return re.sub(r"<[^>]+>", " ", text)


@dataclass
class SearchIndexEntry:
    """A single entry in the semantic search index."""

    search_name: str
    record_type: str
    enriched_text: str


@dataclass
class SemanticSearchIndex:
    """Cosine-similarity index over enriched WDK search descriptions."""

    entries: list[SearchIndexEntry] = field(default_factory=list)
    embeddings: NDArray | None = None

    def build(
        self,
        searches_by_rt: dict[str, list],
        dataset_summaries: dict[str, str] | None = None,
        dataset_contacts: dict[str, str] | None = None,
    ) -> None:
        """Build the index from search catalog data.

        Parameters
        ----------
        searches_by_rt:
            Dict mapping record type name to list of WDKSearch objects.
        dataset_summaries:
            Dict mapping dataset ID to dataset summary text.
        dataset_contacts:
            Dict mapping dataset ID to contact/PI name.
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

        model = _get_model()
        texts = [e.enriched_text for e in self.entries]
        self.embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        logger.info(
            "Semantic search index built",
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
        query_emb = model.encode([query_text], normalize_embeddings=True)
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

        Combines: url_segment (split on underscores/camelCase), display_name,
        short_display_name, summary, description, and dataset metadata
        (summary + contact/PI name) looked up by matching the search name
        to dataset IDs.
        """
        # Split url_segment into words (e.g. "GenesByRNASeqpfal3D7_Su_strand" -> searchable terms)
        name_words = " ".join(re.findall(r"[A-Z][a-z]+|[a-z]+|[A-Z]+|\d+", search.url_segment))

        parts = [
            name_words,
            search.display_name,
            getattr(search, "short_display_name", ""),
            getattr(search, "summary", ""),
            _strip_html(search.description),
        ]

        # Match search name to dataset metadata via dataset ID patterns in the search name
        # E.g. "GenesByRNASeqpfal3D7_Su_strand_specific_rnaSeq_RSRC" -> look for datasets
        # whose summary or contact match
        for ds_id, summary in ds_summaries.items():
            # Check if this dataset's summary mentions terms from the search name
            # or if the search name contains the dataset ID
            if ds_id in search.url_segment:
                parts.append(_strip_html(summary))
                contact = ds_contacts.get(ds_id, "")
                if contact:
                    parts.append(contact)

        # Also do a broader match: find datasets whose primary key appears related
        # by looking for shared substrings between search names and dataset summaries
        search_name_lower = search.url_segment.lower()
        for ds_id, summary in ds_summaries.items():
            if ds_id in search.url_segment:
                continue  # already added above
            # Match dataset ID suffix patterns (e.g. DS_d18037ecc4 won't match search names)
            # Instead, use the dataset primary_key/summary to enrich matching searches
            # by checking if the search display name references the dataset
            summary_lower = summary.lower()
            display_lower = search.display_name.lower()
            # If the display name and dataset summary share significant terms, include it
            display_terms = set(re.findall(r"\b\w{4,}\b", display_lower))
            summary_terms = set(re.findall(r"\b\w{4,}\b", summary_lower))
            overlap = display_terms & summary_terms - {"gene", "genes", "find", "based", "with", "from", "this", "that", "search"}
            if len(overlap) >= 3:
                parts.append(_strip_html(summary))
                contact = ds_contacts.get(ds_id, "")
                if contact:
                    parts.append(contact)

        return " ".join(p for p in parts if p).strip()


def _extract_dataset_id(url: str) -> str | None:
    """Extract dataset ID from a VEuPathDB dataset URL.

    E.g. 'https://PlasmoDB.org/a/app/record/dataset/DS_d18037ecc4' -> 'DS_d18037ecc4'
    """
    m = re.search(r"(DS_[a-f0-9]+)", url)
    return m.group(1) if m else None

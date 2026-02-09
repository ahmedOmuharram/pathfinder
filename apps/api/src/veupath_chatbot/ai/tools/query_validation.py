from __future__ import annotations

from typing import cast

from veupath_chatbot.platform.types import JSONArray, JSONObject

VAGUE_RECORD_TYPE_TOKENS = {
    "gene",
    "genes",
    "transcript",
    "transcripts",
    "record",
    "records",
    "type",
    "types",
    "feature",
    "features",
}


def tokenize_query(text: str) -> list[str]:
    import re

    return re.findall(r"[A-Za-z0-9][A-Za-z0-9._-]{2,}", (text or "").lower())


def record_type_query_error(query: str) -> JSONObject | None:
    """Return an error payload when query is too vague, else None."""
    q = (query or "").strip()
    if not q:
        return None
    tokens = tokenize_query(q)
    if len(tokens) < 2:
        return {
            "error": "query_too_vague",
            "message": "get_record_types(query=...) requires 2+ specific keywords; one-word queries are rejected.",
            "query": q,
            "examples": [
                "gametocyte RNA-seq",
                "single cell atlas",
                "vector salivary gland",
                "metabolic pathway",
            ],
            "avoid": ["gene", "transcript", "record type"],
        }
    # Reject queries made only of generic tokens (e.g. "gene transcript").
    if all(t in VAGUE_RECORD_TYPE_TOKENS for t in tokens):
        return {
            "error": "query_too_vague",
            "message": "Query is too generic; include at least one domain-specific keyword (not only 'gene'/'transcript').",
            "query": q,
            "tokens": cast(JSONArray, tokens),
        }
    return None


def search_query_error(query: str) -> JSONObject | None:
    """Return an error payload when query is too vague, else None."""
    q = (query or "").strip()
    if not q:
        return {
            "error": "query_required",
            "message": "search_for_searches(query=...) requires a non-empty query.",
        }
    tokens = tokenize_query(q)
    if len(tokens) < 2:
        return {
            "error": "query_too_vague",
            "message": "search_for_searches(query=...) requires 2+ specific keywords; one-word/vague queries are rejected.",
            "query": q,
            "examples": [
                "vector salivary gland",
                "gametocyte RNA-seq",
                "drug resistance markers",
                "liver stage expression",
            ],
        }
    return None

"""Reusable search result reranking utilities.

Implements a "fetch wide, rerank narrow" pattern for VEuPathDB search:

1. **Analyse** the query to detect intent (gene ID prefix, organism
   abbreviation, free text, etc.)
2. **Fetch** broadly from one or more sources (site-search, WDK).
3. **Score** each result on multiple relevance signals.
4. **Deduplicate** by primary key, keeping the highest-scored entry.
5. **Return** the top-N results sorted by combined score.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from veupath_chatbot.platform.types import JSONObject


def score_text_match(query: str, value: str) -> float:
    """Score how well *query* matches *value* (0.0--1.0)."""
    q = query.strip().lower()
    v = value.strip().lower()

    if not q or not v:
        return 0.0
    if q == v:
        return 1.0
    if v.startswith(q):
        return 0.90
    if q.startswith(v):
        return 0.70
    if q in v:
        return 0.75

    q_tokens = set(re.split(r"[\s_\-]+", q))
    v_tokens = set(re.split(r"[\s_\-]+", v))
    if q_tokens and v_tokens:
        overlap = len(q_tokens & v_tokens)
        total = max(len(q_tokens), len(v_tokens))
        ratio = overlap / total
        if ratio >= 0.5:
            return 0.60
        if overlap > 0:
            return 0.40
    return 0.0


PRIMARY_MATCH_FIELDS: frozenset[str] = frozenset(
    {
        "gene_source_id",
        "gene_name",
        "gene_product",
        "gene_type",
        "gene_organism_full",
        "primary_key",
        "hyperlinkName",
    }
)

SECONDARY_MATCH_FIELDS: frozenset[str] = frozenset(
    {
        "gene_Notes",
        "gene_PubMed",
        "gene_UserCommentContent",
        "autocomplete",
        "MULTIgene_Notes",
        "MULTIgene_PubMed",
    }
)


def score_field_quality(matched_fields: Sequence[str]) -> float:
    """Score based on *which* fields the query matched in."""
    if not matched_fields:
        return 0.0
    if any(f in PRIMARY_MATCH_FIELDS for f in matched_fields):
        return 1.0
    if any(f in SECONDARY_MATCH_FIELDS for f in matched_fields):
        return -0.5
    return 0.0


@dataclass
class ScoredResult:
    """A search result with an attached relevance score."""

    result: JSONObject
    score: float
    source: str = ""


def dedup_and_sort(
    results: Sequence[ScoredResult],
    key_fn: Callable[[JSONObject], str],
) -> list[ScoredResult]:
    """Deduplicate results by key, keeping the highest-scoring entry."""
    best: dict[str, ScoredResult] = {}
    for sr in results:
        k = key_fn(sr.result)
        if not k:
            continue
        existing = best.get(k)
        if existing is None or sr.score > existing.score:
            best[k] = sr
    return sorted(best.values(), key=lambda x: -x.score)


_GENE_ID_PREFIX_RE = re.compile(
    r"^[A-Za-z]{2,8}[_\-]?\d",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class QueryIntent:
    """What we think the user is looking for."""

    raw: str
    is_gene_id_like: bool = False
    implied_organism: str | None = None
    implied_organism_score: float = 0.0
    wildcard_ids: tuple[str, ...] = ()


def _build_wildcard_ids(query: str) -> tuple[str, ...]:
    """Generate wildcard ID patterns for a gene-ID-like query."""
    q = query.strip()
    if not q:
        return ()

    patterns: list[str] = []
    if "_" in q:
        patterns.append(f"{q}*")
    else:
        upper = q.upper()
        patterns.append(f"{upper}_*")
        patterns.append(f"{upper}*")
        if upper != q:
            patterns.append(f"{q}*")

    return tuple(dict.fromkeys(patterns))


def analyse_query(
    query: str,
    available_organisms: list[str],
    organism_scorer: Callable[[str, str], float] | None = None,
) -> QueryIntent:
    """Analyse a query string to detect search intent.

    :param query: User's raw search text.
    :param available_organisms: Canonical organism names from the site.
    :param organism_scorer: A ``(query, organism) -> float`` scorer.
    :returns: A :class:`QueryIntent` describing what the user likely wants.
    """
    q = query.strip()
    if not q:
        return QueryIntent(raw=q)

    scorer = organism_scorer or _default_organism_scorer
    is_id_like = bool(_GENE_ID_PREFIX_RE.match(q))

    best_org: str | None = None
    best_score: float = 0.0

    for org in available_organisms:
        s = scorer(q, org)
        if s > best_score:
            best_score = s
            best_org = org

    if best_score < 0.60:
        best_org = None
        best_score = 0.0

    wildcard_ids = _build_wildcard_ids(q) if is_id_like else ()

    return QueryIntent(
        raw=q,
        is_gene_id_like=is_id_like,
        implied_organism=best_org,
        implied_organism_score=best_score,
        wildcard_ids=wildcard_ids,
    )


def _default_organism_scorer(query: str, organism: str) -> float:
    """Fallback organism scorer -- simple substring check."""
    q = query.strip().lower()
    o = organism.strip().lower()
    if q == o:
        return 1.0
    if q in o:
        return 0.7
    return 0.0

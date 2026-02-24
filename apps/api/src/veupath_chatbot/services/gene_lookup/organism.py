"""Organism fuzzy matching for gene lookup."""

from __future__ import annotations

import re

from veupath_chatbot.integrations.veupathdb.site_search import strip_html_tags


def score_organism_match(query: str, organism: str) -> float:
    """Score how well *query* matches *organism* (0.0 = no match, 1.0 = exact).

    Handles exact match, substring, genus abbreviation (``P. falciparum``),
    organism codes (``pf3d7``), and token-level overlap.
    """
    q = query.strip().lower()
    o = organism.strip().lower()

    if not q or not o:
        return 0.0
    if q == o:
        return 1.0
    if q in o:
        return 0.85

    abbrev_match = re.match(r"^([a-z])\.?\s+(.+)$", q)
    if abbrev_match:
        genus_initial = abbrev_match.group(1)
        rest = abbrev_match.group(2)
        if o.startswith(genus_initial) and rest in o:
            return 0.80

    o_words = o.split()
    if len(o_words) >= 2:
        gs_initials = o_words[0][0] + o_words[1][0]
        strain_part = "".join(o_words[2:])
        compact = (gs_initials + strain_part).lower()
        q_nospace = (
            q.replace(" ", "")
            .replace(".", "")
            .replace("-", "")
            .replace("_", "")
            .rstrip("*")
        )

        if q_nospace == compact:
            return 0.75
        if q_nospace.startswith(compact) and len(q_nospace) <= len(compact) + 2:
            return 0.72

        if "_" in q:
            prefix = q.split("_", 1)[0].replace(".", "").replace("-", "").lower()
            if prefix == compact:
                return 0.72
            if prefix.startswith(compact) and len(prefix) <= len(compact) + 2:
                return 0.68

    q_tokens = set(q.split())
    o_tokens = set(o.split())
    if q_tokens and q_tokens.issubset(o_tokens):
        return 0.65

    if q_tokens and all(any(qt in ot for ot in o_tokens) for qt in q_tokens):
        return 0.55

    return 0.0


def suggest_organisms(
    query: str,
    available: list[str],
    *,
    max_suggestions: int = 5,
    min_score: float = 0.40,
) -> list[str]:
    """Return organism names from *available* that fuzzy-match *query*.

    :param query: User's organism input.
    :param available: List of canonical organism names (from site-search).
    :param max_suggestions: Maximum suggestions to return.
    :param min_score: Minimum match score to include.
    :returns: Suggested organism names, best match first.
    """
    if not query or not available:
        return []

    scored: list[tuple[float, str]] = []
    for org in available:
        s = score_organism_match(query, org)
        if s >= min_score:
            scored.append((s, org))

    scored.sort(key=lambda x: (-x[0], x[1]))
    return [name for _, name in scored[:max_suggestions]]


def normalize_organism(raw: str) -> str:
    """Clean organism string; handle JSON array format from site-search."""
    s = strip_html_tags(raw or "")
    if not s:
        return ""
    s = s.strip()
    if s.startswith("[") and s.endswith("]"):
        try:
            import json as _json

            parsed = _json.loads(s)
            if isinstance(parsed, list) and parsed:
                return strip_html_tags(str(parsed[0])).strip()
        except ValueError, TypeError:
            pass
    return s

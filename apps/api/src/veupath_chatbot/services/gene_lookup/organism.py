"""Organism fuzzy matching for gene lookup."""

import json
import re

from veupath_chatbot.platform.text import strip_html_tags

_MIN_WORDS_FOR_COMPACT_CODE = 2


def _compact_code(o: str) -> str:
    """Compute a compact organism code from organism name words."""
    o_words = o.split()
    if len(o_words) < _MIN_WORDS_FOR_COMPACT_CODE:
        return ""
    gs_initials = o_words[0][0] + o_words[1][0]
    strain_part = "".join(o_words[2:])
    return (gs_initials + strain_part).lower()


def _normalise_query_code(q: str) -> str:
    """Strip spaces/dots/hyphens/underscores and trailing wildcards from a query."""
    return (
        q.replace(" ", "")
        .replace(".", "")
        .replace("-", "")
        .replace("_", "")
        .rstrip("*")
    )


def _match_compact_code(q_nospace: str, compact: str) -> float:
    """Return score for an exact-or-near match between q_nospace and compact."""
    if q_nospace == compact:
        return 0.75
    if q_nospace.startswith(compact) and len(q_nospace) <= len(compact) + 2:
        return 0.72
    return 0.0


def _score_underscore_prefix(q: str, compact: str) -> float:
    """Score match via the first underscore-delimited prefix of the query."""
    if "_" not in q:
        return 0.0
    prefix = q.split("_", 1)[0].replace(".", "").replace("-", "").lower()
    if prefix == compact:
        return 0.72
    return (
        0.68 if prefix.startswith(compact) and len(prefix) <= len(compact) + 2 else 0.0
    )


def _score_compact_code_match(q: str, o: str) -> float:
    """Score match against organism compact code (e.g. 'pf3d7' for 'Plasmodium falciparum 3D7')."""
    compact = _compact_code(o)
    if not compact:
        return 0.0
    q_nospace = _normalise_query_code(q)
    score = _match_compact_code(q_nospace, compact)
    return score or _score_underscore_prefix(q, compact)


def _score_token_overlap(q_tokens: set[str], o_tokens: set[str]) -> float:
    """Score token-level overlap between query and organism token sets."""
    if not q_tokens:
        return 0.0
    if q_tokens.issubset(o_tokens):
        return 0.65
    return 0.55 if all(any(qt in ot for ot in o_tokens) for qt in q_tokens) else 0.0


def _score_literal_match(q: str, o: str) -> float | None:
    """Return a score if query has an exact/substring/abbreviation match, else None."""
    if q == o or q in o:
        return 1.0 if q == o else 0.85
    abbrev_match = re.match(r"^([a-z])\.?\s+(.+)$", q)
    if (
        abbrev_match
        and o.startswith(abbrev_match.group(1))
        and abbrev_match.group(2) in o
    ):
        return 0.80
    return None


def score_organism_match(query: str, organism: str) -> float:
    """Score how well *query* matches *organism* (0.0 = no match, 1.0 = exact).

    Handles exact match, substring, genus abbreviation (``P. falciparum``),
    organism codes (``pf3d7``), and token-level overlap.
    """
    q = query.strip().lower()
    o = organism.strip().lower()

    if not q or not o:
        return 0.0

    literal = _score_literal_match(q, o)
    if literal is not None:
        return literal

    compact_score = _score_compact_code_match(q, o)
    return (
        compact_score
        if compact_score > 0
        else _score_token_overlap(set(q.split()), set(o.split()))
    )


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
            parsed = json.loads(s)
            if isinstance(parsed, list) and parsed:
                return strip_html_tags(str(parsed[0])).strip()
        except ValueError, TypeError:
            pass
    return s

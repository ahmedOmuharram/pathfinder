"""Search public WDK strategies by text relevance.

Fetches the public strategy list from WDK and ranks by token overlap
against the user's query. Returns the top N matches.
"""

import re

from pathfinder.integrations.embeddings.embed_fn import EmbedFn
from pathfinder.integrations.embeddings.prefixes import (
    SEARCH_DOCUMENT_PREFIX,
    SEARCH_QUERY_PREFIX,
)
from pathfinder.integrations.veupathdb.wdk_models import WDKStrategySummary
from pathfinder.platform.types import JSONObject

# Field weights: name matters most, description second, nameOfFirstStep third.
_FIELD_WEIGHTS: list[tuple[str, float]] = [
    ("name", 3.0),
    ("description", 2.0),
    ("name_of_first_step", 1.0),
    ("author", 0.5),
    ("record_class_name", 0.5),
]

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_MIN_TOKEN_LEN = 2


def _tokenize(text: str) -> set[str]:
    """Lowercase tokenization — split on non-alphanumeric, keep tokens >= 2 chars."""
    return {
        tok for tok in _TOKEN_RE.findall(text.lower()) if len(tok) >= _MIN_TOKEN_LEN
    }


def _score_strategy(strategy: WDKStrategySummary, query_tokens: set[str]) -> float:
    """Score a strategy against query tokens using weighted field overlap."""
    if not query_tokens:
        return 0.0
    total = 0.0
    for field, weight in _FIELD_WEIGHTS:
        value = getattr(strategy, field, "")
        if not value:
            continue
        field_tokens = _tokenize(value)
        if not field_tokens:
            continue
        overlap = len(query_tokens & field_tokens)
        total += weight * (overlap / len(query_tokens))
    return total


def rank_public_strategies(
    strategies: list[WDKStrategySummary],
    query: str,
    limit: int = 3,
) -> list[JSONObject]:
    """Rank public strategies by text relevance to query.

    :param strategies: Typed public strategy summaries from WDK.
    :param query: User's search query.
    :param limit: Maximum results to return.
    :returns: Top matches as serialized dicts, excluding zero-score entries.
    """
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    scored = [
        (strategy, _score_strategy(strategy, query_tokens)) for strategy in strategies
    ]
    scored = [(s, score) for s, score in scored if score > 0]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [
        s.model_dump(by_alias=True, exclude_none=True, mode="json")
        for s, _ in scored[:limit]
    ]


_DEFAULT_SEMANTIC_MIN_SCORE = 0.4


def _strategy_doc(strategy: WDKStrategySummary) -> str:
    return f"{strategy.name}. {strategy.description}. {strategy.name_of_first_step}".strip()


def _cosine(a: list[float], b: list[float]) -> float:
    # embed_text L2-normalizes its output, so cosine similarity == dot product.
    return sum(x * y for x, y in zip(a, b, strict=False))


async def rank_public_strategies_semantic(
    strategies: list[WDKStrategySummary],
    query: str,
    *,
    embed: EmbedFn,
    limit: int = 3,
    min_score: float = _DEFAULT_SEMANTIC_MIN_SCORE,
) -> list[JSONObject]:
    """Rank public strategies by embedding cosine similarity to the query.

    Bridges paraphrase gaps that lexical token overlap misses ("immunization
    targets" vs "vaccine antigens"). The embedding function is injected so this
    stays in the services layer (no AI-layer import) and is pure to test.
    """
    if not strategies or not query.strip():
        return []
    texts = [SEARCH_QUERY_PREFIX + query]
    texts.extend(SEARCH_DOCUMENT_PREFIX + _strategy_doc(s) for s in strategies)
    vectors = await embed(texts)
    query_vec = vectors[0]
    scored: list[tuple[WDKStrategySummary, float]] = []
    for strategy, doc_vec in zip(strategies, vectors[1:], strict=False):
        sim = _cosine(query_vec, doc_vec)
        if sim >= min_score:
            scored.append((strategy, sim))
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [
        s.model_dump(by_alias=True, exclude_none=True, mode="json")
        for s, _ in scored[:limit]
    ]

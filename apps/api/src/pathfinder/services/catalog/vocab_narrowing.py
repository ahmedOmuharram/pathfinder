"""Shortlist a vocabulary so a model can read it.

The portal's InterPro vocabulary is 12,113 entries, about 219K tokens; it can
never travel whole. Embeddings rank the options against the criterion text and
only the top slice is sent.

The split is deliberate. Ranking is a **recall** job: if the right option misses
the shortlist the resolver answers "not determinable" and a question gets asked.
Letting the same embeddings **decide** is what bound `PF00069` to
`IPR000023 : Phosphofructokinase_dom` -- far fewer genes than intended, with verification
reporting success. Recall failures are visible; decision failures are silent.
"""

from __future__ import annotations

from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.integrations.embeddings.embed_fn import EmbedFn
from pathfinder.integrations.embeddings.prefixes import (
    SEARCH_DOCUMENT_PREFIX,
    SEARCH_QUERY_PREFIX,
)

# Below this, the whole vocabulary is cheap enough to send and ranking can only
# lose information. 200 options is roughly 4K tokens.
DIRECT_MAX = 200
# The shortlist a large vocabulary is reduced to. Same order as DIRECT_MAX so the
# model sees a comparable amount either way.
TOP_K = 200


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=False))


def _named_verbatim(options: list[VocabOption], text: str) -> list[VocabOption]:
    """Options whose value appears literally in the criterion text.

    An identifier the user wrote is not a similarity question. If embeddings rank
    it 12,000th it must still reach the resolver, or the shortlist excludes the
    only right answer.
    """
    low = text.casefold()
    return [o for o in options if o.value.casefold() in low]


async def narrow_candidates(
    options: list[VocabOption],
    text: str,
    *,
    embed: EmbedFn,
) -> list[VocabOption]:
    """The slice of ``options`` a resolver should choose from."""
    if len(options) <= DIRECT_MAX:
        return options

    pinned = _named_verbatim(options, text)
    texts = [SEARCH_QUERY_PREFIX + text]
    texts.extend(SEARCH_DOCUMENT_PREFIX + (o.display or o.value) for o in options)
    vectors = await embed(texts)
    query = vectors[0]
    ranked = sorted(
        zip(options, vectors[1:], strict=False),
        key=lambda pair: _cosine(query, pair[1]),
        reverse=True,
    )

    shortlist: list[VocabOption] = list(pinned)
    seen = {o.value for o in shortlist}
    for option, _ in ranked:
        if len(shortlist) >= TOP_K:
            break
        if option.value not in seen:
            shortlist.append(option)
            seen.add(option.value)
    return shortlist[:TOP_K]

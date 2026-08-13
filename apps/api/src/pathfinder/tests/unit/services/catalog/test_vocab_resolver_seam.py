"""The last resort is a model that reads the vocabulary, not a cosine threshold.

`_semantic_value` decided 108 of the 237 gold parameters that no named rule
covers, on a 0.45 similarity score between the whole criterion sentence and each
option's display string. It is the component that bound `PF00069` to
`IPR000023 : Phosphofructokinase_dom`.

It is replaced by an injected ``VocabResolver``: services stay free of ``ai/``
imports, tests inject a fake, and the luna-backed implementation lives in the AI
layer. Two properties matter more than the substitution itself:

* the resolver may only return a value it was shown, and
* ``None`` means "ask", never "take WDK's default" -- the silent-wrong-answer
  path is the whole reason this change exists.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.integrations.embeddings.embed_fn import EmbedFn
from pathfinder.services.catalog.param_formatting import ParameterInfo
from pathfinder.services.catalog.param_intent import (
    NO_RESOLVERS,
    ParamIntent,
    ValueResolvers,
    map_intent_to_value,
)


async def _value(
    pi: ParameterInfo,
    intent: ParamIntent,
    *,
    embed: EmbedFn,
    resolvers: ValueResolvers = NO_RESOLVERS,
) -> str | list[str] | None:
    """The resolved value alone. Provenance is asserted separately."""
    match = await map_intent_to_value(pi, intent, embed=embed, resolvers=resolvers)
    return match.value if match else None


_OPTIONS = [
    VocabOption(value="yes", display="yes"),
    VocabOption(value="no", display="no"),
]


def _param(
    name: str = "some_choice", options: list[VocabOption] | None = None
) -> ParameterInfo:
    return ParameterInfo(
        name=name,
        display_name=name,
        type="single-pick-vocabulary",
        required=True,
        is_visible=True,
        help="",
        value_format="",
        allowed_values=_OPTIONS if options is None else options,
    )


async def _embed(texts: Sequence[str]) -> list[list[float]]:
    return [[0.0, 0.0] for _ in texts]


def _resolver_returning(value: str | None, seen: list[list[VocabOption]] | None = None):
    async def resolve(
        text: str, pi: ParameterInfo, candidates: list[VocabOption]
    ) -> str | None:
        del text, pi
        if seen is not None:
            seen.append(candidates)
        return value

    return resolve


class TestTheResolverDecides:
    @pytest.mark.asyncio
    async def test_its_answer_is_used(self) -> None:
        resolved = await _value(
            _param(),
            ParamIntent(text="anything"),
            embed=_embed,
            resolvers=ValueResolvers(vocab=_resolver_returning("no")),
        )

        assert resolved == "no"

    @pytest.mark.asyncio
    async def test_it_receives_the_vocabulary(self) -> None:
        seen: list[list[VocabOption]] = []

        await _value(
            _param(),
            ParamIntent(text="anything"),
            embed=_embed,
            resolvers=ValueResolvers(vocab=_resolver_returning("yes", seen)),
        )

        assert len(seen) == 1
        assert {o.value for o in seen[0]} == {"yes", "no"}


class TestNullMeansAsk:
    @pytest.mark.asyncio
    async def test_none_is_returned_rather_than_a_guess(self) -> None:
        resolved = await _value(
            _param(),
            ParamIntent(text="nothing relevant here"),
            embed=_embed,
            resolvers=ValueResolvers(vocab=_resolver_returning(None)),
        )

        assert resolved is None


class TestItCannotInventValues:
    @pytest.mark.asyncio
    async def test_a_value_outside_the_vocabulary_is_refused(self) -> None:
        # A resolver that answers with something it was not shown is a bug in
        # the resolver; the seam must not pass it through to WDK.
        resolved = await _value(
            _param(),
            ParamIntent(text="anything"),
            embed=_embed,
            resolvers=ValueResolvers(vocab=_resolver_returning("Non-syntenic")),
        )

        assert resolved is None


class TestTheNamedRulesStillWinFirst:
    @pytest.mark.asyncio
    async def test_polarity_beats_the_resolver(self) -> None:
        # Structural rules are cheaper and deterministic; the resolver is the
        # last resort, not the first.
        resolved = await _value(
            _param("isSyntenic"),
            ParamIntent(text="non-syntenic orthologs"),
            embed=_embed,
            resolvers=ValueResolvers(vocab=_resolver_returning("yes")),
        )

        assert resolved == "no"

    @pytest.mark.asyncio
    async def test_an_accession_in_the_vocabulary_beats_the_resolver(self) -> None:
        options = [
            VocabOption(value="PF00069", display="Pkinase"),
            VocabOption(value="PF00072", display="Response_reg"),
        ]

        resolved = await _value(
            _param("domain", options),
            ParamIntent(text="domain PF00069"),
            embed=_embed,
            resolvers=ValueResolvers(vocab=_resolver_returning("PF00072")),
        )

        assert resolved == "PF00069"

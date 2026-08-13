"""A range in the request must bind every term it covers, or bind nothing.

"trophozoite time points (20-32 hours)" names thirteen of the DeRisi sample
vocabulary's 46 hour terms. Two defects kept it a question:

* a tree-box param keeps its values in ``vocab_leaves`` rather than
  ``allowed_values``, so it fell between the vocabulary branch (which read
  ``allowed_values``) and the vocabulary-less branch (which requires both to be
  empty), and reached neither resolver; and
* the resolver answered one value, while ``param_value_for`` wraps a single term
  into a one-element list for a multi-pick -- so "20 Hour" would have bound ONE
  hour where the request asks for thirteen.

The second is why they had to land together. A partially-correct multi-pick is
the worst outcome available here: it looks answered, it validates, and it
silently searches a narrower question than the one asked. So any element that
does not match a candidate refuses the whole answer.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.services.catalog.param_formatting import ParameterInfo
from pathfinder.services.catalog.param_intent import (
    ParamIntent,
    ValueResolvers,
    map_intent_to_value,
)

_HOURS = [VocabOption(value=f"{h} Hour", display=f"{h} Hour") for h in range(1, 47)]
_TROPHOZOITE = [f"{h} Hour" for h in range(20, 33)]


def _tree_box(name: str = "samples_percentile_generic") -> ParameterInfo:
    """A tree-box multi-pick: values live in ``vocab_leaves``, not
    ``allowed_values``. This is the shape that reached no resolver."""
    return ParameterInfo(
        name=name,
        display_name="Samples",
        type="multi-pick-vocabulary",
        required=True,
        is_visible=True,
        help="",
        value_format="",
        vocab_leaves=_HOURS,
    )


def _single_pick() -> ParameterInfo:
    return ParameterInfo(
        name="profileset_generic",
        display_name="Profile set",
        type="single-pick-vocabulary",
        required=True,
        is_visible=True,
        help="",
        value_format="",
        allowed_values=[
            VocabOption(value="DeRisi 3D7 Smoothed", display="3D7"),
            VocabOption(value="DeRisi HB3 Smoothed", display="HB3"),
        ],
    )


async def _embed(texts: Sequence[str]) -> list[list[float]]:
    return [[0.0, 0.0] for _ in texts]


def _resolver(answer: object, seen: list[ParameterInfo] | None = None):
    async def resolve(
        text: str, pi: ParameterInfo, candidates: list[VocabOption]
    ) -> object:
        del text, candidates
        if seen is not None:
            seen.append(pi)
        return answer

    return resolve


async def _resolve(pi: ParameterInfo, answer: object, text: str = "20-32 hours"):
    match = await map_intent_to_value(
        pi,
        ParamIntent(text=text),
        embed=_embed,
        resolvers=ValueResolvers(vocab=_resolver(answer)),
    )
    return match.value if match else None


class TestATreeBoxParamReachesTheResolver:
    @pytest.mark.asyncio
    async def test_its_leaves_are_offered_as_candidates(self) -> None:
        seen: list[ParameterInfo] = []
        await map_intent_to_value(
            _tree_box(),
            ParamIntent(text="20-32 hours"),
            embed=_embed,
            resolvers=ValueResolvers(vocab=_resolver(["20 Hour"], seen)),
        )

        assert seen, "a tree-box param never reached the resolver at all"

    @pytest.mark.asyncio
    async def test_the_resolver_sees_which_param_it_is_answering(self) -> None:
        # Without the param, the resolver is guessing which of several vocabularies
        # in a criterion it is choosing for.
        seen: list[ParameterInfo] = []
        await map_intent_to_value(
            _tree_box(),
            ParamIntent(text="20-32 hours"),
            embed=_embed,
            resolvers=ValueResolvers(vocab=_resolver(["20 Hour"], seen)),
        )

        assert seen[0].name == "samples_percentile_generic"


class TestARangeBindsEveryTerm:
    @pytest.mark.asyncio
    async def test_thirteen_hours_survive_as_thirteen(self) -> None:
        resolved = await _resolve(_tree_box(), _TROPHOZOITE)

        assert resolved == _TROPHOZOITE

    @pytest.mark.asyncio
    async def test_a_single_term_answer_is_still_a_list(self) -> None:
        resolved = await _resolve(_tree_box(), ["20 Hour"])

        assert resolved == ["20 Hour"]


class TestPartialAnswersAreRefused:
    @pytest.mark.asyncio
    async def test_one_bad_element_refuses_the_whole_answer(self) -> None:
        # Keeping the twelve good ones would silently search a narrower question
        # than the one asked, and nothing downstream could tell.
        resolved = await _resolve(_tree_box(), [*_TROPHOZOITE, "99 Hour"])

        assert resolved is None

    @pytest.mark.asyncio
    async def test_an_empty_answer_is_a_question(self) -> None:
        assert await _resolve(_tree_box(), []) is None

    @pytest.mark.asyncio
    async def test_null_is_a_question(self) -> None:
        assert await _resolve(_tree_box(), None) is None


class TestSinglePickStaysSingle:
    @pytest.mark.asyncio
    async def test_a_single_value_resolves(self) -> None:
        resolved = await _resolve(
            _single_pick(), ["DeRisi 3D7 Smoothed"], text="DeRisi 3D7"
        )

        assert resolved == "DeRisi 3D7 Smoothed"

    @pytest.mark.asyncio
    async def test_two_values_for_a_single_pick_are_refused(self) -> None:
        resolved = await _resolve(
            _single_pick(),
            ["DeRisi 3D7 Smoothed", "DeRisi HB3 Smoothed"],
            text="DeRisi",
        )

        assert resolved is None, "a single-pick param cannot take two values"


class TestAMultiPickTooLargeToSeeWholeIsNotGuessed:
    """Shortlisting is safe for a single pick and unsafe for a set.

    Measured against live vocabularies: `GenesByReactionCompounds.chebi_compound_id` has
    five figures entries, `GenesByGoTerm.go_typeahead` thousands, and
    `GenesByInterproDomain.domain_typeahead` thousands -- all multi-pick. If the
    model is shown the top 200 of five figures, every value it returns validates, so
    an answer that is missing 90% of what the criterion covers is
    indistinguishable from a complete one.

    A single pick has no such problem: one right answer either survives the
    shortlist or it does not, and a miss becomes a question.
    """

    @staticmethod
    def _huge_multi() -> ParameterInfo:
        return ParameterInfo(
            name="chebi_compound_id",
            display_name="Compounds",
            type="multi-pick-vocabulary",
            required=True,
            is_visible=True,
            help="",
            value_format="",
            vocab_leaves=[
                VocabOption(value=f"CHEBI:{i}", display=f"c{i}") for i in range(1000)
            ],
        )

    @pytest.mark.asyncio
    async def test_it_asks_instead_of_answering_from_a_shortlist(self) -> None:
        answered: list[bool] = []

        async def resolve(
            text: str, pi: ParameterInfo, candidates: list[VocabOption]
        ) -> object:
            del text, pi, candidates
            answered.append(True)
            return ["CHEBI:1", "CHEBI:2"]

        resolved = await map_intent_to_value(
            self._huge_multi(),
            ParamIntent(text="all sugar compounds"),
            embed=_embed,
            resolvers=ValueResolvers(vocab=resolve),
        )

        assert resolved is None
        assert not answered, "the resolver must not be asked to pick a subset"

    @pytest.mark.asyncio
    async def test_a_single_pick_that_large_still_resolves(self) -> None:
        big_single = ParameterInfo(
            name="domain",
            display_name="Domain",
            type="single-pick-vocabulary",
            required=True,
            is_visible=True,
            help="",
            value_format="",
            vocab_leaves=[
                VocabOption(value=f"IPR{i:06}", display=f"d{i}") for i in range(1000)
            ],
        )

        async def resolve(
            text: str, pi: ParameterInfo, candidates: list[VocabOption]
        ) -> object:
            del text, pi
            return candidates[0].value

        resolved = await map_intent_to_value(
            big_single,
            ParamIntent(text="a domain"),
            embed=_embed,
            resolvers=ValueResolvers(vocab=resolve),
        )

        assert resolved is not None

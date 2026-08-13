"""A yes/no param named for the positive must read a negated request.

Observed on a multi-criterion request: "transform to P. falciparum 3D7 **non-syntenic**
orthologs". `GenesByOrthologs.isSyntenic` is a single-pick vocabulary of exactly
`['yes', 'no']`. Nothing mapped the phrasing to the vocabulary, so the model
supplied its own wording and WDK answered:

    Parameter 'isSyntenic' does not accept 'Non-syntenic'.

That burned a `set_criterion` call out of a budget the turn then ran out of, and
on a smaller problem it would instead have silently taken the `no` default while
the user asked for something the default happens to match -- right answer, wrong
reason, and the opposite request would have been wrong outright.

The param name carries the concept (`isSyntenic` -> "syntenic"); the criterion
text carries the polarity. Both are already present, so nothing needs guessing.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.services.catalog.param_formatting import ParameterInfo
from pathfinder.services.catalog.param_intent import ParamIntent, map_intent_to_value


def _yes_no(name: str) -> ParameterInfo:
    return ParameterInfo(
        name=name,
        display_name=name,
        type="single-pick-vocabulary",
        required=True,
        is_visible=True,
        help="",
        value_format="",
        allowed_values=[
            VocabOption(value="yes", display="yes"),
            VocabOption(value="no", display="no"),
        ],
    )


async def _embed(texts: Sequence[str]) -> list[list[float]]:
    # Orthogonal to everything, so nothing resolves by similarity and the rule
    # under test is the only thing that can answer.
    return [[0.0, 0.0] for _ in texts]


async def _resolve(name: str, text: str) -> str | list[str] | None:
    match = await map_intent_to_value(
        _yes_no(name), ParamIntent(text=text), embed=_embed
    )
    return match.value if match else None


class TestNegatedRequest:
    @pytest.mark.asyncio
    async def test_non_hyphen_prefix_reads_as_no(self) -> None:
        assert await _resolve("isSyntenic", "non-syntenic orthologs") == "no"

    @pytest.mark.asyncio
    async def test_non_as_a_separate_word_reads_as_no(self) -> None:
        assert await _resolve("isSyntenic", "non syntenic orthologs") == "no"

    @pytest.mark.asyncio
    async def test_not_reads_as_no(self) -> None:
        assert await _resolve("isSyntenic", "orthologs that are not syntenic") == "no"

    @pytest.mark.asyncio
    async def test_snake_case_param_name_also_works(self) -> None:
        assert await _resolve("is_syntenic", "non-syntenic orthologs") == "no"


class TestPlainRequest:
    @pytest.mark.asyncio
    async def test_a_plain_mention_reads_as_yes(self) -> None:
        assert await _resolve("isSyntenic", "syntenic orthologs only") == "yes"

    @pytest.mark.asyncio
    async def test_the_concept_must_actually_appear(self) -> None:
        # Saying nothing about synteny must not silently pick a side; the
        # param's own default is the right answer and the walk applies it.
        assert await _resolve("isSyntenic", "kinases expressed in trophozoites") is None


class TestItDoesNotOverreach:
    @pytest.mark.asyncio
    async def test_a_non_boolean_vocabulary_is_untouched(self) -> None:
        param = ParameterInfo(
            name="isSyntenic",
            display_name="isSyntenic",
            type="single-pick-vocabulary",
            required=True,
            is_visible=True,
            help="",
            value_format="",
            allowed_values=[
                VocabOption(value="syntenic", display="syntenic"),
                VocabOption(value="non-syntenic", display="non-syntenic"),
                VocabOption(value="either", display="either"),
            ],
        )

        # Three options is not a polarity question; leave it to the other tiers.
        resolved = await map_intent_to_value(
            param, ParamIntent(text="non-syntenic orthologs"), embed=_embed
        )

        assert resolved != "no"

    @pytest.mark.asyncio
    async def test_a_negation_elsewhere_in_the_text_is_not_the_signal(self) -> None:
        # "absent in humans" is a different clause; it must not flip synteny.
        assert (
            await _resolve("isSyntenic", "syntenic orthologs, absent in humans")
            == "yes"
        )

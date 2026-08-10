"""An identifier stated in the request answers a param that has no vocabulary.

Live PlasmoDB, the 16-step prompt: "Identify kinases ... **EC number 2.7.-.-**".
FRAME bound the criterion, then BUILD stopped:

    These criteria still need user-supplied parameters: kinase_ec.ec_wildcard

and the Lead asked the user to confirm `2.7.-.-` -- the value they had already
written. `GenesByEcNumber.ec_wildcard` is a visible required `string` with no
vocabulary and the placeholder default `'N/A'`, so refusing the default is right
(see numeric-default-is-not-an-example for the mirror case) but asking is not.

`accession_in_text` already recognizes this shape; it just matches only against
vocabulary options, so a param with no vocabulary could never be answered by it.
With no options to validate against, the literal the user wrote IS the value, and
WDK is the thing that validates it.

Ambiguity still yields a slot: two identifiers in one criterion means we cannot
tell which one this param wants.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.services.catalog.param_formatting import ParameterInfo
from pathfinder.services.catalog.param_intent import ParamIntent, map_intent_to_value


def _vocabless(name: str = "ec_wildcard") -> ParameterInfo:
    return ParameterInfo(
        name=name,
        display_name=name,
        type="string",
        required=True,
        is_visible=True,
        help="",
        value_format="",
        default_value="N/A",
    )


async def _embed(texts: Sequence[str]) -> list[list[float]]:
    return [[0.0, 0.0] for _ in texts]


async def _resolve(param: ParameterInfo, text: str) -> str | None:
    return await map_intent_to_value(param, ParamIntent(text=text), embed=_embed)


class TestTheIdentifierIsTaken:
    @pytest.mark.asyncio
    async def test_an_ec_wildcard_is_read_from_the_request(self) -> None:
        resolved = await _resolve(
            _vocabless(), "kinases by EC number 2.7.-.- across Plasmodium"
        )

        assert resolved == "2.7.-.-"

    @pytest.mark.asyncio
    async def test_a_full_ec_number_is_read_too(self) -> None:
        assert await _resolve(_vocabless(), "enzymes with EC 2.7.11.1") == "2.7.11.1"

    @pytest.mark.asyncio
    async def test_a_pfam_accession_is_read(self) -> None:
        assert await _resolve(_vocabless("domain_id"), "domain PF00069") == "PF00069"


class TestItStillAsksWhenItShould:
    @pytest.mark.asyncio
    async def test_no_identifier_means_no_answer(self) -> None:
        # A free-text query ("text search for 'kinase'") carries no identifier,
        # so it stays a question rather than inheriting WDK's example default.
        assert await _resolve(_vocabless("text_expression"), "text search for kinase") is None

    @pytest.mark.asyncio
    async def test_two_identifiers_are_ambiguous(self) -> None:
        resolved = await _resolve(
            _vocabless(), "EC 2.7.-.- and InterPro PF00069 together"
        )

        assert resolved is None, "cannot tell which identifier this param wants"

    @pytest.mark.asyncio
    async def test_a_param_with_a_vocabulary_is_untouched(self) -> None:
        # With options present, `accession_in_text` owns this and only accepts
        # an identifier the vocabulary actually contains.
        param = ParameterInfo(
            name="domain_typeahead",
            display_name="domain",
            type="single-pick-vocabulary",
            required=True,
            is_visible=True,
            help="",
            value_format="",
            allowed_values=[VocabOption(value="IPR000719", display="Protein kinase")],
        )

        assert await _resolve(param, "domain PF00069") is None

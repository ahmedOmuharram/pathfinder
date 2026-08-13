"""An identifier only answers a param that could hold it."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.services.catalog.param_formatting import ParameterInfo
from pathfinder.services.catalog.param_intent import ParamIntent, map_intent_to_value

_TEXT = "differential expression in strain SC5314 with adjusted p-value 0.1"


def _vocabless(name: str, *, is_number: bool = False) -> ParameterInfo:
    return ParameterInfo(
        name=name,
        display_name=name,
        type="string",
        required=True,
        is_visible=True,
        help="",
        value_format="",
        is_number=is_number,
    )


async def _embed(texts: Sequence[str]) -> list[list[float]]:
    return [[0.0, 0.0] for _ in texts]


async def _resolve(pi: ParameterInfo, text: str = _TEXT) -> str | list[str] | None:
    match = await map_intent_to_value(pi, ParamIntent(text=text), embed=_embed)
    return match.value if match else None


class TestANumericParamRefusesANonNumber:
    @pytest.mark.asyncio
    async def test_a_strain_name_does_not_become_a_p_value(self) -> None:
        assert await _resolve(_vocabless("adj_p_value", is_number=True)) is None

    @pytest.mark.asyncio
    async def test_a_strain_name_does_not_become_a_fold_change(self) -> None:
        assert await _resolve(_vocabless("fold_change", is_number=True)) is None

    @pytest.mark.asyncio
    async def test_a_numeric_param_still_takes_a_numeric_identifier(self) -> None:
        resolved = await _resolve(
            _vocabless("ec_number", is_number=True), "EC number 2.7.11.1"
        )

        assert resolved == "2.7.11.1"


class TestANonNumericParamIsUnaffected:
    @pytest.mark.asyncio
    async def test_an_accession_still_answers_a_text_param(self) -> None:
        assert await _resolve(_vocabless("domain_id"), "domain PF00069") == "PF00069"

    @pytest.mark.asyncio
    async def test_an_ec_wildcard_still_answers(self) -> None:
        assert (
            await _resolve(_vocabless("ec_wildcard"), "EC number 2.7.-.-") == "2.7.-.-"
        )


class TestAVocabularyOwnsItsIdentifier:
    """A search can offer the same identifier a real vocabulary and a spare
    string field. The vocabulary is where the value belongs."""

    @staticmethod
    def _typeahead() -> ParameterInfo:
        return ParameterInfo(
            name="go_typeahead",
            display_name="GO term",
            type="multi-pick-vocabulary",
            required=True,
            is_visible=True,
            help="",
            value_format="",
            vocab_leaves=[VocabOption(value="GO:0016301", display="kinase activity")],
        )

    @pytest.mark.asyncio
    async def test_a_spare_string_field_does_not_take_it(self) -> None:
        resolved = await map_intent_to_value(
            _vocabless("go_term"),
            ParamIntent(text="GO term kinase activity (GO:0016301)"),
            embed=_embed,
            siblings=[self._typeahead()],
        )

        assert resolved is None

    @pytest.mark.asyncio
    async def test_the_vocabulary_param_still_takes_it(self) -> None:
        match = await map_intent_to_value(
            self._typeahead(),
            ParamIntent(text="GO term kinase activity (GO:0016301)"),
            embed=_embed,
        )

        assert match is not None
        assert match.value == "GO:0016301"

    @pytest.mark.asyncio
    async def test_without_such_a_sibling_the_string_field_still_takes_it(self) -> None:
        resolved = await _resolve(_vocabless("ec_wildcard"), "EC number 2.7.-.-")

        assert resolved == "2.7.-.-"

"""A term the request puts in quotes answers the search's free-text query."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from pathfinder.services.catalog.param_formatting import ParameterInfo
from pathfinder.services.catalog.param_intent import ParamIntent, map_intent_to_value


def _query(name: str = "text_expression", *, required: bool = True) -> ParameterInfo:
    return ParameterInfo(
        name=name,
        display_name=name,
        type="string",
        required=required,
        is_visible=True,
        help="",
        value_format="",
        default_value="*reductase",
    )


def _hidden_switch() -> ParameterInfo:
    return ParameterInfo(
        name="document_type",
        display_name="document_type",
        type="string",
        required=True,
        is_visible=False,
        help="",
        value_format="",
        default_value="gene",
    )


async def _embed(texts: Sequence[str]) -> list[list[float]]:
    return [[0.0, 0.0] for _ in texts]


async def _resolve(pi: ParameterInfo, text: str) -> str | list[str] | None:
    match = await map_intent_to_value(pi, ParamIntent(text=text), embed=_embed)
    return match.value if match else None


class TestTheQuotedTermIsTaken:
    @pytest.mark.asyncio
    async def test_single_quotes(self) -> None:
        assert await _resolve(_query(), "text search for 'kinase'") == "kinase"

    @pytest.mark.asyncio
    async def test_double_quotes(self) -> None:
        assert await _resolve(_query(), 'text search for "kinase"') == "kinase"

    @pytest.mark.asyncio
    async def test_a_two_word_term(self) -> None:
        resolved = await _resolve(_query(), "annotation text matching 'protein kinase'")

        assert resolved == "protein kinase"


class TestItStaysNarrow:
    @pytest.mark.asyncio
    async def test_two_quoted_spans_are_ambiguous(self) -> None:
        resolved = await _resolve(_query(), "match 'kinase' but not 'phosphatase'")

        assert resolved is None

    @pytest.mark.asyncio
    async def test_a_quoted_sentence_is_not_a_search_term(self) -> None:
        resolved = await _resolve(
            _query(),
            "genes described as 'involved in the regulation of transcription "
            "during the asexual blood stage of the parasite life cycle'",
        )

        assert resolved is None

    @pytest.mark.asyncio
    async def test_a_hidden_switch_keeps_its_default(self) -> None:
        # Hidden params are internal plumbing, not the user's query.
        assert await _resolve(_hidden_switch(), "text search for 'kinase'") is None

    @pytest.mark.asyncio
    async def test_no_quotes_still_asks(self) -> None:
        assert await _resolve(_query(), "text search for kinase") is None

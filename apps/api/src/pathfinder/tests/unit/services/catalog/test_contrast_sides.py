"""In "A vs B", A is the comparator and B is the reference."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.services.catalog.param_formatting import ParameterInfo
from pathfinder.services.catalog.param_intent import ParamIntent, map_intent_to_value

_OPTIONS = [
    VocabOption(value="G0 EX VIVO CSF", display="G0 EX VIVO CSF"),
    VocabOption(value="HC1 EX VIVO CSF", display="HC1 EX VIVO CSF"),
]
_LABEL = "HC1 vs G0 ex vivo CSF (paired-end)"


def _side(name: str) -> ParameterInfo:
    return ParameterInfo(
        name=name,
        display_name=name,
        type="multi-pick-vocabulary",
        required=True,
        is_visible=True,
        help="",
        value_format="",
        allowed_values=_OPTIONS,
    )


async def _embed(texts: Sequence[str]) -> list[list[float]]:
    return [[0.0, 0.0] for _ in texts]


async def _resolve(name: str, text: str = _LABEL) -> str | list[str] | None:
    match = await map_intent_to_value(_side(name), ParamIntent(text=text), embed=_embed)
    return match.value if match else None


class TestTheMarkerDecidesTheSide:
    @pytest.mark.asyncio
    async def test_the_comparator_is_named_before_the_marker(self) -> None:
        assert await _resolve("samples_fc_comp_generic") == "HC1 EX VIVO CSF"

    @pytest.mark.asyncio
    async def test_versus_spelled_out_works_too(self) -> None:
        resolved = await _resolve(
            "samples_fc_comp_generic", "HC1 versus G0 ex vivo CSF"
        )

        assert resolved == "HC1 EX VIVO CSF"

    @pytest.mark.asyncio
    async def test_compared_to_works_too(self) -> None:
        resolved = await _resolve(
            "samples_fc_comp_generic", "HC1 compared to G0 ex vivo CSF"
        )

        assert resolved == "HC1 EX VIVO CSF"


class TestWithoutAMarker:
    @pytest.mark.asyncio
    async def test_a_single_named_group_is_still_the_comparator(self) -> None:
        resolved = await _resolve(
            "samples_fc_comp_generic", "genes enriched in HC1 EX VIVO CSF"
        )

        assert resolved == "HC1 EX VIVO CSF"

    @pytest.mark.asyncio
    async def test_the_reference_side_is_not_guessed_from_the_subject(self) -> None:
        # The criterion names what should be enriched, which is the comparator.
        assert await _resolve("samples_fc_ref_generic") is None

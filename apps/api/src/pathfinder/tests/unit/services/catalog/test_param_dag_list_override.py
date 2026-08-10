"""A multi-pick override must stay a list all the way to the typed value.

The DeRisi trophozoite criterion answered its open slot with the natural
``["20 Hour", ..., "32 Hour"]``. That list was serialized to WDK wire form at
the tool boundary, so the resolver received the single string
``'["20 Hour", "21 Hour", ...]'``, matched it against the vocabulary as ONE
option, found nothing, and passed it through. Validation then reported:

    Parameter 'samples_percentile_generic' does not accept
    '["20 Hour", "21 Hour", ... "32 Hour"]'

with a validOptions list that contains every one of those hours. The model was
told its own correct answer was invalid, and offered to build 13 separate
search arms instead.

``param_value_from_raw`` has always handled a list -- ``_curated_multi_default``
feeds it one. Only the ``str`` annotations and the early serialization stood in
the way.
"""

from __future__ import annotations

import pytest

from pathfinder.domain.parameters.values import MultiPickValue
from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.services.catalog.param_dag import (
    ResolvedParams,
    _apply_override,
    resolve_params_with_intent,
)
from pathfinder.services.catalog.param_formatting import ParameterInfo
from pathfinder.services.catalog.param_intent import ParamIntent

_HOURS = [f"{h} Hour" for h in range(1, 49)]
_TROPHOZOITE = [f"{h} Hour" for h in range(20, 33)]


def _samples_param() -> ParameterInfo:
    return ParameterInfo(
        name="samples_percentile_generic",
        display_name="Samples",
        type="multi-pick-vocabulary",
        required=True,
        is_visible=True,
        help="",
        value_format="",
        vocab_leaves=[VocabOption(value=h, display=h) for h in _HOURS],
    )


async def _embed(texts: list[str]) -> list[list[float]]:
    return [[1.0, 0.0] for _ in texts]


async def _resolve(overrides: dict[str, str | list[str]]) -> ResolvedParams:
    async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
        del context
        return [_samples_param()]

    return await resolve_params_with_intent(
        fetch_at=fetch_at,
        intent=ParamIntent(organism_scope=None, text="trophozoite stage"),
        embed=_embed,
        overrides=overrides,
    )


class TestApplyOverride:
    def test_matches_every_element_of_a_list(self) -> None:
        matched = _apply_override(_samples_param(), _TROPHOZOITE)

        assert matched == _TROPHOZOITE

    def test_snaps_each_element_to_its_vocabulary_entry(self) -> None:
        # Single values already snap ("20 hour" -> "20 Hour"); a list must not
        # lose that just because it arrived as a list.
        matched = _apply_override(_samples_param(), ["20 hour", "21 HOUR"])

        assert matched == ["20 Hour", "21 Hour"]

    def test_keeps_an_unmatched_element_for_wdk_to_reject(self) -> None:
        matched = _apply_override(_samples_param(), ["20 Hour", "99 Hour"])

        assert matched == ["20 Hour", "99 Hour"]

    def test_still_handles_a_plain_string(self) -> None:
        assert _apply_override(_samples_param(), "20 Hour") == "20 Hour"

    def test_an_empty_list_stays_empty(self) -> None:
        assert _apply_override(_samples_param(), []) == []


class TestResolvedValue:
    @pytest.mark.asyncio
    async def test_a_list_override_becomes_a_multi_pick_value(self) -> None:
        rp = await _resolve({"samples_percentile_generic": _TROPHOZOITE})

        value = rp.params["samples_percentile_generic"]
        assert isinstance(value, MultiPickValue)
        assert value.values == _TROPHOZOITE

    @pytest.mark.asyncio
    async def test_does_not_collapse_the_list_into_one_option(self) -> None:
        rp = await _resolve({"samples_percentile_generic": _TROPHOZOITE})

        value = rp.params["samples_percentile_generic"]
        assert isinstance(value, MultiPickValue)
        assert len(value.values) == len(_TROPHOZOITE), (
            "a serialized array counted as a single value, which is what WDK "
            "then rejected"
        )

    @pytest.mark.asyncio
    async def test_closes_the_open_slot(self) -> None:
        rp = await _resolve({"samples_percentile_generic": _TROPHOZOITE})

        assert rp.open_slots == []
        assert rp.unresolved_required == []

    @pytest.mark.asyncio
    async def test_a_single_element_list_is_still_a_list(self) -> None:
        rp = await _resolve({"samples_percentile_generic": ["20 Hour"]})

        value = rp.params["samples_percentile_generic"]
        assert isinstance(value, MultiPickValue)
        assert value.values == ["20 Hour"]

    @pytest.mark.asyncio
    async def test_a_scalar_override_still_resolves(self) -> None:
        rp = await _resolve({"samples_percentile_generic": "20 Hour"})

        value = rp.params["samples_percentile_generic"]
        assert isinstance(value, MultiPickValue)
        assert value.values == ["20 Hour"]

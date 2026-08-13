"""A bound value carries where it came from, and a guess does not bind."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.services.catalog.param_dag import resolve_params_with_intent
from pathfinder.services.catalog.param_formatting import ParameterInfo
from pathfinder.services.catalog.param_intent import (
    ParamIntent,
    Provenance,
    ValueResolvers,
    map_intent_to_value,
)

_OPTIONS = [
    VocabOption(value="ring", display="ring"),
    VocabOption(value="trophozoite", display="trophozoite"),
]


def _param(name: str = "stage", default: str | None = None) -> ParameterInfo:
    return ParameterInfo(
        name=name,
        display_name=name,
        type="single-pick-vocabulary",
        required=True,
        is_visible=True,
        help="",
        value_format="",
        default_value=default,
        allowed_values=_OPTIONS,
    )


def _organism() -> ParameterInfo:
    return ParameterInfo(
        name="organism",
        display_name="Organism",
        type="single-pick-vocabulary",
        required=True,
        is_visible=True,
        help="",
        value_format="",
        allowed_values=[
            VocabOption(
                value="Plasmodium falciparum 3D7", display="Plasmodium falciparum 3D7"
            ),
            VocabOption(value="Plasmodium vivax P01", display="Plasmodium vivax P01"),
        ],
    )


async def _embed(texts: Sequence[str]) -> list[list[float]]:
    return [[0.0, 0.0] for _ in texts]


def _guesser(answer: str):
    async def resolve(
        text: str, pi: ParameterInfo, candidates: list[VocabOption]
    ) -> str:
        del text, pi, candidates
        return answer

    return resolve


class TestTheReaderReportsHowItFound:
    @pytest.mark.asyncio
    async def test_a_resolver_answer_is_inferred(self) -> None:
        match = await map_intent_to_value(
            _param(),
            ParamIntent(text="anything"),
            embed=_embed,
            resolvers=ValueResolvers(vocab=_guesser("ring")),
        )

        assert match is not None
        assert match.value == "ring"
        assert match.provenance is Provenance.INFERRED

    @pytest.mark.asyncio
    async def test_a_value_named_in_the_request_is_stated(self) -> None:
        match = await map_intent_to_value(
            _organism(),
            ParamIntent(text="in Plasmodium falciparum 3D7"),
            embed=_embed,
        )

        assert match is not None
        assert match.value == "Plasmodium falciparum 3D7"
        assert match.provenance is Provenance.STATED


async def _walk(
    param: ParameterInfo,
    *,
    resolvers: ValueResolvers,
    bind_inferred: bool = False,
):
    async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
        del context
        return [param]

    return await resolve_params_with_intent(
        fetch_at=fetch_at,
        intent=ParamIntent(text="anything"),
        embed=_embed,
        resolvers=resolvers,
        bind_inferred=bind_inferred,
    )


class TestAGuessDoesNotBind:
    @pytest.mark.asyncio
    async def test_it_falls_through_to_the_default(self) -> None:
        resolved = await _walk(
            _param(default="ring"),
            resolvers=ValueResolvers(vocab=_guesser("trophozoite")),
        )

        assert resolved.provenance["stage"] is Provenance.DEFAULTED
        assert "trophozoite" not in str(resolved.params["stage"])

    @pytest.mark.asyncio
    async def test_without_a_default_it_becomes_a_question(self) -> None:
        resolved = await _walk(
            _param(), resolvers=ValueResolvers(vocab=_guesser("trophozoite"))
        )

        assert "stage" not in resolved.params
        assert [s.param_name for s in resolved.open_slots] == ["stage"]

    @pytest.mark.asyncio
    async def test_it_binds_when_explicitly_allowed(self) -> None:
        # The benchmark measures both arms, so the policy stays switchable.
        resolved = await _walk(
            _param(),
            resolvers=ValueResolvers(vocab=_guesser("trophozoite")),
            bind_inferred=True,
        )

        assert resolved.provenance["stage"] is Provenance.INFERRED


class TestDefaultsAreDisclosable:
    @pytest.mark.asyncio
    async def test_a_defaulted_param_is_listed(self) -> None:
        resolved = await _walk(_param(default="ring"), resolvers=ValueResolvers())

        assert resolved.defaulted() == ["stage"]

    @pytest.mark.asyncio
    async def test_a_stated_param_is_not_listed(self) -> None:
        resolved = await resolve_params_with_intent(
            fetch_at=_only(_organism()),
            intent=ParamIntent(text="in Plasmodium falciparum 3D7"),
            embed=_embed,
        )

        assert resolved.defaulted() == []


def _only(param: ParameterInfo):
    async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
        del context
        return [param]

    return fetch_at

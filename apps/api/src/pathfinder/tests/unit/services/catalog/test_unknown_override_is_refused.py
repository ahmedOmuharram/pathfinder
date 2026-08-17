"""An override that names no parameter is an error, not a silent no-op."""

from __future__ import annotations

import pytest

from pathfinder.domain.parameters.values import SinglePickValue
from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.platform.errors import ErrorCode, ValidationError
from pathfinder.services.catalog.param_dag import (
    UnknownParameterError,
    resolve_params_with_intent,
)
from pathfinder.services.catalog.param_formatting import ParameterInfo
from pathfinder.services.catalog.param_intent import ParamIntent


def _pct() -> ParameterInfo:
    return ParameterInfo(
        name="min_expression_percentile",
        display_name="Min pct",
        type="string",
        required=True,
        is_visible=True,
        is_number=True,
        help="",
        value_format="",
        default_value="80",
    )


def _stage() -> ParameterInfo:
    return ParameterInfo(
        name="stage",
        display_name="Stage",
        type="single-pick-vocabulary",
        required=True,
        is_visible=True,
        help="",
        value_format="",
        vocab_leaves=[
            VocabOption(value="gametocyte", display="Gametocyte"),
            VocabOption(value="ring", display="Ring"),
        ],
    )


async def _fetch_pct(context: dict[str, str]) -> list[ParameterInfo]:
    del context
    return [_pct()]


@pytest.mark.asyncio
async def test_a_misspelled_override_raises_with_the_real_names() -> None:
    with pytest.raises(UnknownParameterError) as info:
        await resolve_params_with_intent(
            fetch_at=_fetch_pct,
            intent=ParamIntent(text="top 10 percent"),
            overrides={"min_percentile": "90"},
        )

    assert info.value.unknown == ["min_percentile"]
    assert info.value.valid == ["min_expression_percentile"]


@pytest.mark.asyncio
async def test_it_is_a_validation_error_carrying_every_unknown_name() -> None:
    async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
        del context
        return [_pct(), _stage()]

    with pytest.raises(UnknownParameterError) as info:
        await resolve_params_with_intent(
            fetch_at=fetch_at,
            intent=ParamIntent(text="top 10 percent"),
            overrides={"percentile": "90", "life_stage": "gametocyte"},
        )

    exc = info.value
    assert isinstance(exc, ValidationError)
    assert exc.code is ErrorCode.VALIDATION_ERROR
    assert exc.unknown == ["life_stage", "percentile"]
    assert exc.valid == ["min_expression_percentile", "stage"]
    assert exc.errors == [{"param": "life_stage"}, {"param": "percentile"}]
    assert exc.detail is not None
    assert "min_expression_percentile" in exc.detail


@pytest.mark.asyncio
async def test_a_known_override_still_resolves() -> None:
    async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
        del context
        return [_stage()]

    rp = await resolve_params_with_intent(
        fetch_at=fetch_at,
        intent=ParamIntent(text="anything"),
        overrides={"stage": "Gametocyte"},
    )

    value = rp.params["stage"]
    assert isinstance(value, SinglePickValue)
    assert value.value == "gametocyte"


@pytest.mark.asyncio
async def test_no_overrides_never_raises() -> None:
    rp = await resolve_params_with_intent(
        fetch_at=_fetch_pct,
        intent=ParamIntent(text="anything"),
    )

    assert "min_expression_percentile" in rp.params


@pytest.mark.asyncio
async def test_an_override_for_a_dependent_param_is_not_refused() -> None:
    # A param whose vocabulary depends on a parent is still named on the first
    # fetch, so overriding it must not read as an unknown name.
    async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
        allowed = (
            [VocabOption(value="gametocyte", display="Gametocyte")]
            if "profileset" in context
            else []
        )
        return [
            ParameterInfo(
                name="profileset",
                display_name="Profile set",
                type="single-pick-vocabulary",
                required=True,
                is_visible=True,
                help="",
                value_format="",
                vocab_leaves=[VocabOption(value="ps1", display="Profile Set 1")],
            ),
            ParameterInfo(
                name="stage",
                display_name="Stage",
                type="single-pick-vocabulary",
                required=True,
                is_visible=True,
                help="",
                value_format="",
                vocab_leaves=allowed,
                vocab_depends_on=["profileset"],
            ),
        ]

    rp = await resolve_params_with_intent(
        fetch_at=fetch_at,
        intent=ParamIntent(text="anything"),
        overrides={"stage": "gametocyte"},
    )

    value = rp.params["stage"]
    assert isinstance(value, SinglePickValue)
    assert value.value == "gametocyte"

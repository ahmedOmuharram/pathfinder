"""With no override the walk binds a default or opens a slot; it reads no English."""

from __future__ import annotations

import pytest

from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.services.catalog.param_dag import (
    ParamFetcher,
    resolve_params_with_intent,
)
from pathfinder.services.catalog.param_formatting import ParameterInfo
from pathfinder.services.catalog.param_intent import ParamIntent, Provenance

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


def _only(param: ParameterInfo) -> ParamFetcher:
    async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
        del context
        return [param]

    return fetch_at


@pytest.mark.asyncio
async def test_without_an_override_a_vocabulary_param_is_a_default_or_a_slot() -> None:
    stage = _param(default="ring")
    resolved = await resolve_params_with_intent(
        fetch_at=_only(stage), intent=ParamIntent(text="trophozoite stage")
    )
    assert resolved.provenance["stage"] is Provenance.DEFAULTED

    resolved = await resolve_params_with_intent(
        fetch_at=_only(_param()), intent=ParamIntent(text="trophozoite stage")
    )
    assert [s.param_name for s in resolved.open_slots] == ["stage"]


@pytest.mark.asyncio
async def test_an_override_binds_as_stated() -> None:
    resolved = await resolve_params_with_intent(
        fetch_at=_only(_param()),
        intent=ParamIntent(text=""),
        overrides={"stage": "trophozoite"},
    )
    assert resolved.provenance["stage"] is Provenance.STATED


@pytest.mark.asyncio
async def test_a_defaulted_param_is_listed() -> None:
    resolved = await resolve_params_with_intent(
        fetch_at=_only(_param(default="ring")), intent=ParamIntent(text="anything")
    )

    assert resolved.defaulted() == ["stage"]


@pytest.mark.asyncio
async def test_a_stated_param_is_not_listed() -> None:
    resolved = await resolve_params_with_intent(
        fetch_at=_only(_param()),
        intent=ParamIntent(text="anything"),
        overrides={"stage": "ring"},
    )

    assert resolved.defaulted() == []

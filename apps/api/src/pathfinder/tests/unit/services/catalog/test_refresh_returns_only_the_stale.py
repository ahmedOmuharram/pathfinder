"""The refresh endpoint answers with the stale dependents and nothing else.

A parameter that is absent was not asked about. An empty array is neither a
failure nor a confirmation.
"""

from __future__ import annotations

from typing import cast

import pytest
from assistant_core.platform.types import JSONObject
from pydantic import JsonValue

from pathfinder.domain.parameters.specs import ParamSpecNormalized
from pathfinder.domain.parameters.values import ParamValue, SinglePickValue
from pathfinder.domain.search import SearchContext
from pathfinder.integrations.veupathdb.wdk_parameters import WDKEnumParam, WDKParameter
from pathfinder.platform.errors import AppError, ErrorCode
from pathfinder.services.catalog import param_validation as pv

_CTX = SearchContext(
    site_id="plasmodb", record_type="transcript", search_name="GenesByProfile"
)
_STATIC = [["20 Hour", "20 Hour", None], ["30 Hour", "30 Hour", None]]
_REFRESHED = [["7 Hour", "7 Hour", None]]


def _wdk_param(name: str, vocab: list[list[str | None]]) -> WDKParameter:
    raw: JSONObject = {
        "type": "multi-pick-vocabulary",
        "name": name,
        "display_name": name,
        "vocabulary": cast("JsonValue", vocab),
        "allow_empty_value": False,
    }
    return cast("WDKParameter", WDKEnumParam.model_validate(raw))


def _spec(name: str, *, dependents: tuple[str, ...] = ()) -> ParamSpecNormalized:
    return ParamSpecNormalized(
        name=name, param_type="multi-pick-vocabulary", dependent_params=dependents
    )


def _specs() -> dict[str, ParamSpecNormalized]:
    return {
        "profileset": _spec("profileset", dependents=("samples",)),
        "samples": _spec("samples"),
        "any_or_all": _spec("any_or_all"),
    }


def _values() -> dict[str, ParamValue]:
    return {"profileset": SinglePickValue(value="DeRisi 3D7 Smoothed")}


def _answering(
    monkeypatch: pytest.MonkeyPatch, params: list[WDKParameter]
) -> list[str]:
    asked: list[str] = []

    async def _refresh(
        ctx: SearchContext, *, parameter_name: str, context_values: JSONObject
    ) -> list[WDKParameter]:
        del ctx, context_values
        asked.append(parameter_name)
        return params

    monkeypatch.setattr(pv, "get_refreshed_dependent_params", _refresh)
    return asked


async def _refreshed_specs() -> dict[str, ParamSpecNormalized]:
    return await pv._refresh_dependent_vocabularies(
        ctx=_CTX, param_spec_map=_specs(), canonical_values=_values()
    )


class TestWhatComesBackIsMergedOver:
    @pytest.mark.asyncio
    async def test_the_returned_dependent_replaces_its_spec(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _answering(monkeypatch, [_wdk_param("samples", _REFRESHED)])

        specs = await _refreshed_specs()

        assert specs["samples"].vocabulary is not None

    @pytest.mark.asyncio
    async def test_only_the_parent_with_dependents_is_asked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        asked = _answering(monkeypatch, [_wdk_param("samples", _REFRESHED)])

        await _refreshed_specs()

        assert asked == ["profileset"]


class TestWhatDoesNotComeBackIsLeftAlone:
    @pytest.mark.asyncio
    async def test_an_empty_array_changes_nothing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _answering(monkeypatch, [])

        assert await _refreshed_specs() == _specs()

    @pytest.mark.asyncio
    async def test_an_unmentioned_param_keeps_its_spec(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _answering(monkeypatch, [_wdk_param("samples", _REFRESHED)])

        specs = await _refreshed_specs()

        assert specs["any_or_all"] == _spec("any_or_all")

    @pytest.mark.asyncio
    async def test_a_param_that_is_not_a_declared_dependent_is_ignored(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _answering(monkeypatch, [_wdk_param("any_or_all", _REFRESHED)])

        specs = await _refreshed_specs()

        assert specs["any_or_all"] == _spec("any_or_all")


class TestAFailedRefreshKeepsTheStaticVocabulary:
    @pytest.mark.asyncio
    async def test_an_error_does_not_empty_the_specs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _raise(
            ctx: SearchContext, *, parameter_name: str, context_values: JSONObject
        ) -> list[WDKParameter]:
            del ctx, parameter_name, context_values
            raise AppError(code=ErrorCode.WDK_ERROR, title="refresh failed", status=502)

        monkeypatch.setattr(pv, "get_refreshed_dependent_params", _raise)

        assert await _refreshed_specs() == _specs()


class TestAParentWithNoValueIsNotAsked:
    @pytest.mark.asyncio
    async def test_an_unset_parent_is_skipped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        asked = _answering(monkeypatch, [_wdk_param("samples", _STATIC)])

        await pv._refresh_dependent_vocabularies(
            ctx=_CTX, param_spec_map=_specs(), canonical_values={}
        )

        assert asked == []

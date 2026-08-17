"""A branch term is legal input and WDK counts only leaves.

Under ``countOnlyLeaves`` WDK scores a branch selection as zero values, so the
branch must become its leaves before WDK is asked to judge the values.
"""

from __future__ import annotations

import json
from typing import Any, cast

import pytest
from pydantic import JsonValue

from pathfinder.domain.parameters.values import MultiPickValue, ParamValue
from pathfinder.domain.search import SearchContext
from pathfinder.integrations.veupathdb.wdk_models import (
    StepValidation,
    WDKSearch,
    WDKSearchResponse,
)
from pathfinder.integrations.veupathdb.wdk_parameters import WDKEnumParam, WDKParameter
from pathfinder.platform.errors import ValidationError
from pathfinder.platform.types import JSONObject
from pathfinder.services.catalog import param_validation as pv

_CTX = SearchContext(
    site_id="plasmodb", record_type="transcript", search_name="GenesByProfile"
)
_LEAVES = ["17 Hour", "18 Hour", "19 Hour"]


def _tree() -> JSONObject:
    return cast(
        "JSONObject",
        {
            "data": {"term": "@@fake@@", "display": "@@fake@@"},
            "children": [
                {
                    "data": {"term": "Trophozoite", "display": "17-30 Hours"},
                    "children": [
                        {"data": {"term": leaf, "display": leaf}} for leaf in _LEAVES
                    ],
                }
            ],
        },
    )


def _samples(echoed: str) -> WDKParameter:
    raw: JSONObject = {
        "type": "multi-pick-vocabulary",
        "name": "samples",
        "display_name": "Samples",
        "display_type": "treeBox",
        "count_only_leaves": True,
        "vocabulary": cast("JsonValue", _tree()),
        "allow_empty_value": False,
        "initial_display_value": echoed,
    }
    return cast("WDKParameter", WDKEnumParam.model_validate(raw))


def _response(*, rejects_samples: bool, echoed: str) -> WDKSearchResponse:
    errors = (
        {
            "general": [],
            "byKey": {
                "samples": [
                    "Number of selected values (0) is not allowed."
                    "  Must be within ( 1, unlimited )"
                ]
            },
        }
        if rejects_samples
        else None
    )
    return WDKSearchResponse(
        search_data=WDKSearch(
            url_segment="GenesByProfile",
            full_name="GenesByProfile",
            display_name="Genes by profile",
            param_names=["samples"],
            parameters=[_samples(echoed)],
        ),
        validation=StepValidation.model_validate(
            {"level": "SEMANTIC", "isValid": not rejects_samples, "errors": errors}
        ),
    )


class _WDK:
    """Rejects a branch selection the way WDK does, and records every ask."""

    def __init__(self) -> None:
        self.asked: list[dict[str, str]] = []

    async def __call__(
        self,
        ctx: SearchContext,
        *,
        resolved_record_type: str,
        parameters: dict[str, ParamValue],
    ) -> pv.ResolvedSearch:
        del ctx, resolved_record_type
        sent = pv.encode_wdk_params(parameters)
        self.asked.append(sent)
        picked = json.loads(sent.get("samples", "[]"))
        leaf_count = len([v for v in picked if v in _LEAVES])
        # WDK echoes the leaves it read, in its own order.
        echoed = json.dumps(sorted(picked, reverse=True))
        return pv.ResolvedSearch(
            response=_response(rejects_samples=leaf_count == 0, echoed=echoed),
            values_were_read=True,
        )


def _callbacks() -> pv.ValidationCallbacks:
    async def _resolve(
        record_type: str | None,
        search_name: str | None,
        *,
        require_match: bool = False,
        allow_fallback: bool = False,
    ) -> str | None:
        del search_name, require_match, allow_fallback
        return record_type

    async def _hint(search_name: str, record_type: str | None) -> str | None:
        del search_name, record_type
        return None

    return pv.ValidationCallbacks(
        resolve_record_type_for_search=_resolve, find_record_type_hint=_hint
    )


async def _no_refresh(
    ctx: SearchContext, *, parameter_name: str, context_values: JSONObject
) -> list[WDKParameter]:
    del ctx, parameter_name, context_values
    return []


@pytest.fixture
def wdk(monkeypatch: pytest.MonkeyPatch) -> _WDK:
    stub = _WDK()
    monkeypatch.setattr(pv, "_resolve_search_details", stub)
    monkeypatch.setattr(pv, "get_refreshed_dependent_params", _no_refresh)
    return stub


async def _validate(values: list[str]) -> Any:
    return await pv.validate_parameters(
        _CTX,
        parameters={"samples": MultiPickValue(values=values)},
        callbacks=_callbacks(),
    )


class TestABranchTermIsAccepted:
    @pytest.mark.asyncio
    async def test_it_does_not_raise(self, wdk: _WDK) -> None:
        assert await _validate(["Trophozoite"]) is not None

    @pytest.mark.asyncio
    async def test_it_becomes_the_leaves(self, wdk: _WDK) -> None:
        result = await _validate(["Trophozoite"])

        assert result.params["samples"] == MultiPickValue(values=_LEAVES)

    @pytest.mark.asyncio
    async def test_wdk_judges_the_leaves_not_the_branch(self, wdk: _WDK) -> None:
        # WDK counts only leaves, so its verdict on the branch is about a value
        # we were about to replace.
        await _validate(["Trophozoite"])

        assert json.loads(wdk.asked[-1]["samples"]) == _LEAVES

    @pytest.mark.asyncio
    async def test_the_leaves_are_not_reported_as_substituted(self, wdk: _WDK) -> None:
        # The echo is the same selection in another order, not WDK's own value.
        result = await _validate(["Trophozoite"])

        assert result.substituted == []


class TestALeafSelectionIsUnchanged:
    @pytest.mark.asyncio
    async def test_leaves_pass_straight_through(self, wdk: _WDK) -> None:
        result = await _validate(["17 Hour", "18 Hour"])

        assert result.params["samples"] == MultiPickValue(values=["17 Hour", "18 Hour"])

    @pytest.mark.asyncio
    async def test_no_second_ask_when_nothing_changed(self, wdk: _WDK) -> None:
        await _validate(["17 Hour", "18 Hour"])

        assert len(wdk.asked) == 1


class TestARealRejectionStillRaises:
    @pytest.mark.asyncio
    async def test_a_term_in_no_branch_is_reported(self, wdk: _WDK) -> None:
        with pytest.raises(ValidationError):
            await _validate(["99 Hour"])

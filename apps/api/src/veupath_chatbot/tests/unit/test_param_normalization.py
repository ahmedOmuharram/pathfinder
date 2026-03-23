"""Tests for parameter normalization in strategy compilation."""

import json
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from veupath_chatbot.domain.parameters.specs import ParamSpecNormalized
from veupath_chatbot.domain.strategy.ast import PlanStepNode, StrategyAST
from veupath_chatbot.domain.strategy.compile import StrategyCompiler
from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKIdentifier,
    WDKSearchResponse,
)
from veupath_chatbot.integrations.veupathdb.wdk_parameters import WDKEnumParam
from veupath_chatbot.platform.types import JSONObject, as_json_object

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "wdk"


def _load_fixture(name: str) -> JSONObject:
    with (FIXTURES_DIR / name).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
        if not isinstance(data, dict):
            msg = f"Fixture {name} is not a JSON object"
            raise TypeError(msg)
        return as_json_object(data)


class FakeStrategyAPI:
    """Minimal StrategyAPI stub for compilation tests."""

    def __init__(self, fixtures: dict[str, JSONObject]) -> None:
        self.client = MagicMock()

        async def get_search_details(
            record_type: str, search_name: str, expand_params: bool = False
        ) -> WDKSearchResponse:
            return WDKSearchResponse.model_validate(fixtures[search_name])

        self.client.get_search_details = AsyncMock(side_effect=get_search_details)
        self.client.get_searches = AsyncMock(return_value=[])
        self.client.get_record_types = AsyncMock(return_value=[])
        self.client.get_search_details_with_params = AsyncMock(
            side_effect=get_search_details
        )
        self.create_step = AsyncMock(return_value=WDKIdentifier(id=101))
        self.create_transform_step = AsyncMock(return_value=WDKIdentifier(id=202))
        self.create_combined_step = AsyncMock(return_value=WDKIdentifier(id=303))
        self._resolved_user_id = "test_user"


def test_param_specs_treat_negative_max_as_unlimited() -> None:
    param = WDKEnumParam(
        name="organism",
        type="multi-pick-vocabulary",
        max_selected_count=-1,
    )
    spec = ParamSpecNormalized.from_wdk(param)
    assert spec.max_selected_count is None


@pytest.mark.asyncio
async def test_compile_search_normalizes_multi_pick_params() -> None:
    fixtures = {"GenesWithEpitopes": _load_fixture("genes_with_epitopes.json")}
    api = FakeStrategyAPI(fixtures)
    compiler = StrategyCompiler(cast("StrategyAPI", api), resolve_record_type=False)

    step = PlanStepNode(
        search_name="GenesWithEpitopes",
        parameters={
            "organism": ["Plasmodium"],
            "epitope_confidence": ["High", "Medium"],
        },
        display_name="Epitope Search",
    )
    strategy = StrategyAST(record_type="transcript", root=step)

    await compiler.compile(strategy)

    api.create_step.assert_awaited_once()
    spec = api.create_step.call_args.args[0]
    params = spec.search_config.parameters
    assert params["organism"] == json.dumps(["Plasmodium"])
    assert params["epitope_confidence"] == json.dumps(["High", "Medium"])


@pytest.mark.asyncio
async def test_compile_search_accepts_csv_multi_pick_params() -> None:
    fixtures = {"GenesWithEpitopes": _load_fixture("genes_with_epitopes.json")}
    api = FakeStrategyAPI(fixtures)
    compiler = StrategyCompiler(cast("StrategyAPI", api), resolve_record_type=False)

    step = PlanStepNode(
        search_name="GenesWithEpitopes",
        parameters={
            "organism": "Plasmodium, Plasmodium falciparum 3D7",
            "epitope_confidence": "High,Medium",
        },
    )
    strategy = StrategyAST(record_type="transcript", root=step)

    await compiler.compile(strategy)

    spec = api.create_step.call_args.args[0]
    params = spec.search_config.parameters
    assert params["organism"] == json.dumps(["Plasmodium", "Plasmodium falciparum 3D7"])
    assert params["epitope_confidence"] == json.dumps(["High", "Medium"])


@pytest.mark.asyncio
async def test_compile_search_accepts_bracketed_csv_values() -> None:
    fixtures = {"GenesWithEpitopes": _load_fixture("genes_with_epitopes.json")}
    api = FakeStrategyAPI(fixtures)
    compiler = StrategyCompiler(cast("StrategyAPI", api), resolve_record_type=False)

    step = PlanStepNode(
        search_name="GenesWithEpitopes",
        parameters={
            "organism": "['Plasmodium', 'Plasmodium falciparum 3D7']",
            "epitope_confidence": "['High', 'Medium']",
        },
    )
    strategy = StrategyAST(record_type="transcript", root=step)

    await compiler.compile(strategy)

    spec = api.create_step.call_args.args[0]
    params = spec.search_config.parameters
    assert params["organism"] == json.dumps(["Plasmodium", "Plasmodium falciparum 3D7"])
    assert params["epitope_confidence"] == json.dumps(["High", "Medium"])


@pytest.mark.asyncio
async def test_compile_transform_clears_input_step_param() -> None:
    fixtures = {
        "GenesWithEpitopes": _load_fixture("genes_with_epitopes.json"),
        "GenesByOrthologs": _load_fixture("genes_by_orthologs.json"),
    }
    api = FakeStrategyAPI(fixtures)
    compiler = StrategyCompiler(cast("StrategyAPI", api), resolve_record_type=False)

    search = PlanStepNode(
        search_name="GenesWithEpitopes",
        parameters={
            "organism": ["Plasmodium"],
            "epitope_confidence": ["High"],
        },
    )
    transform = PlanStepNode(
        search_name="GenesByOrthologs",
        primary_input=search,
        parameters={
            "organism": ["Plasmodium falciparum 3D7"],
            "isSyntenic": "no",
        },
        display_name="Orthologs",
    )
    strategy = StrategyAST(record_type="transcript", root=transform)

    await compiler.compile(strategy)

    api.create_transform_step.assert_awaited_once()
    spec = api.create_transform_step.call_args.args[0]
    params = spec.search_config.parameters
    assert params["organism"] == json.dumps(["Plasmodium falciparum 3D7"])
    assert params["isSyntenic"] == "no"
    assert params["inputStepId"] == ""

"""Tests for parameter normalization in strategy compilation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock

import pytest

from veupath_chatbot.domain.parameters.specs import adapt_param_specs
from veupath_chatbot.domain.strategy.ast import PlanStepNode, StrategyAST
from veupath_chatbot.domain.strategy.compile import StrategyCompiler
from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.platform.types import JSONObject

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "wdk"


def _load_fixture(name: str) -> JSONObject:
    from veupath_chatbot.platform.types import as_json_object

    with (FIXTURES_DIR / name).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError(f"Fixture {name} is not a JSON object")
        return as_json_object(data)


class FakeStrategyAPI:
    """Minimal StrategyAPI stub for compilation tests."""

    def __init__(self, fixtures: dict[str, JSONObject]) -> None:
        from unittest.mock import MagicMock

        self.client = MagicMock()

        async def get_search_details(
            record_type: str, search_name: str, expand_params: bool = False
        ) -> JSONObject:
            return fixtures[search_name]

        self.client.get_search_details = AsyncMock(side_effect=get_search_details)
        self.client.get_searches = AsyncMock(return_value=[])
        self.client.get_record_types = AsyncMock(return_value=[])
        self.client.get_search_details_with_params = AsyncMock(
            side_effect=get_search_details
        )
        self.create_step = AsyncMock(return_value={"id": 101})
        self.create_transform_step = AsyncMock(return_value={"id": 202})
        self.create_combined_step = AsyncMock(return_value={"id": 303})
        self.user_id = "test_user"


def test_param_specs_treat_negative_max_as_unlimited() -> None:
    specs = adapt_param_specs(
        {
            "parameters": [
                {
                    "name": "organism",
                    "type": "multi-pick-vocabulary",
                    "maxSelectedCount": -1,
                }
            ]
        }
    )
    assert specs["organism"].max_selected_count is None


@pytest.mark.asyncio
async def test_compile_search_normalizes_multi_pick_params() -> None:
    fixtures = {"GenesWithEpitopes": _load_fixture("genes_with_epitopes.json")}
    api = FakeStrategyAPI(fixtures)
    compiler = StrategyCompiler(cast(StrategyAPI, api), resolve_record_type=False)

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
    _, kwargs = api.create_step.call_args
    params = kwargs["parameters"]
    assert params["organism"] == json.dumps(["Plasmodium"])
    assert params["epitope_confidence"] == json.dumps(["High", "Medium"])


@pytest.mark.asyncio
async def test_compile_search_accepts_csv_multi_pick_params() -> None:
    fixtures = {"GenesWithEpitopes": _load_fixture("genes_with_epitopes.json")}
    api = FakeStrategyAPI(fixtures)
    compiler = StrategyCompiler(cast(StrategyAPI, api), resolve_record_type=False)

    step = PlanStepNode(
        search_name="GenesWithEpitopes",
        parameters={
            "organism": "Plasmodium, Plasmodium falciparum 3D7",
            "epitope_confidence": "High,Medium",
        },
    )
    strategy = StrategyAST(record_type="transcript", root=step)

    await compiler.compile(strategy)

    _, kwargs = api.create_step.call_args
    params = kwargs["parameters"]
    assert params["organism"] == json.dumps(["Plasmodium", "Plasmodium falciparum 3D7"])
    assert params["epitope_confidence"] == json.dumps(["High", "Medium"])


@pytest.mark.asyncio
async def test_compile_search_accepts_bracketed_csv_values() -> None:
    fixtures = {"GenesWithEpitopes": _load_fixture("genes_with_epitopes.json")}
    api = FakeStrategyAPI(fixtures)
    compiler = StrategyCompiler(cast(StrategyAPI, api), resolve_record_type=False)

    step = PlanStepNode(
        search_name="GenesWithEpitopes",
        parameters={
            "organism": "['Plasmodium', 'Plasmodium falciparum 3D7']",
            "epitope_confidence": "['High', 'Medium']",
        },
    )
    strategy = StrategyAST(record_type="transcript", root=step)

    await compiler.compile(strategy)

    _, kwargs = api.create_step.call_args
    params = kwargs["parameters"]
    assert params["organism"] == json.dumps(["Plasmodium", "Plasmodium falciparum 3D7"])
    assert params["epitope_confidence"] == json.dumps(["High", "Medium"])


@pytest.mark.asyncio
async def test_compile_transform_clears_input_step_param() -> None:
    fixtures = {
        "GenesWithEpitopes": _load_fixture("genes_with_epitopes.json"),
        "GenesByOrthologs": _load_fixture("genes_by_orthologs.json"),
    }
    api = FakeStrategyAPI(fixtures)
    compiler = StrategyCompiler(cast(StrategyAPI, api), resolve_record_type=False)

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
    _, kwargs = api.create_transform_step.call_args
    params = kwargs["parameters"]
    assert params["organism"] == json.dumps(["Plasmodium falciparum 3D7"])
    assert params["isSyntenic"] == "no"
    assert params["inputStepId"] == ""

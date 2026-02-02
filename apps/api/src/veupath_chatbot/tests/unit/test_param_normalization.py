"""Tests for parameter normalization in strategy compilation."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from veupath_chatbot.domain.parameters.specs import adapt_param_specs
from veupath_chatbot.domain.strategy.ast import SearchStep, StrategyAST, TransformStep
from veupath_chatbot.domain.strategy.compile import StrategyCompiler


FIXTURES_DIR = (
    Path(__file__).resolve().parent.parent / "fixtures" / "wdk"
)


def _load_fixture(name: str) -> dict:
    with (FIXTURES_DIR / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


class FakeStrategyAPI:
    """Minimal StrategyAPI stub for compilation tests."""

    def __init__(self, fixtures: dict[str, dict]) -> None:
        self.client = AsyncMock()

        async def get_search_details(record_type, search_name, expand_params=False):
            return fixtures[search_name]

        self.client.get_search_details.side_effect = get_search_details
        self.create_step = AsyncMock(return_value={"id": 101})
        self.create_transform_step = AsyncMock(return_value={"id": 202})


def test_param_specs_treat_negative_max_as_unlimited():
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
async def test_compile_search_normalizes_multi_pick_params():
    fixtures = {"GenesWithEpitopes": _load_fixture("genes_with_epitopes.json")}
    api = FakeStrategyAPI(fixtures)
    compiler = StrategyCompiler(api, resolve_record_type=False)

    step = SearchStep(
        record_type="transcript",
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
async def test_compile_search_accepts_csv_multi_pick_params():
    fixtures = {"GenesWithEpitopes": _load_fixture("genes_with_epitopes.json")}
    api = FakeStrategyAPI(fixtures)
    compiler = StrategyCompiler(api, resolve_record_type=False)

    step = SearchStep(
        record_type="transcript",
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
    assert params["organism"] == json.dumps(
        ["Plasmodium", "Plasmodium falciparum 3D7"]
    )
    assert params["epitope_confidence"] == json.dumps(["High", "Medium"])


@pytest.mark.asyncio
async def test_compile_search_accepts_bracketed_csv_values():
    fixtures = {"GenesWithEpitopes": _load_fixture("genes_with_epitopes.json")}
    api = FakeStrategyAPI(fixtures)
    compiler = StrategyCompiler(api, resolve_record_type=False)

    step = SearchStep(
        record_type="transcript",
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
    assert params["organism"] == json.dumps(
        ["Plasmodium", "Plasmodium falciparum 3D7"]
    )
    assert params["epitope_confidence"] == json.dumps(["High", "Medium"])


@pytest.mark.asyncio
async def test_compile_transform_clears_input_step_param():
    fixtures = {
        "GenesWithEpitopes": _load_fixture("genes_with_epitopes.json"),
        "GenesByOrthologs": _load_fixture("genes_by_orthologs.json"),
    }
    api = FakeStrategyAPI(fixtures)
    compiler = StrategyCompiler(api, resolve_record_type=False)

    search = SearchStep(
        record_type="transcript",
        search_name="GenesWithEpitopes",
        parameters={
            "organism": ["Plasmodium"],
            "epitope_confidence": ["High"],
        },
    )
    transform = TransformStep(
        transform_name="GenesByOrthologs",
        input=search,
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

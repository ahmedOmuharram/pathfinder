"""Three unrelated things called filters, and a level the schema forbids.

Nothing in the name of a "filter" says which mechanism it belongs to, and the
platform emits a validation level its own step schema rejects.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pathfinder.domain.parameters.values import FilterTermClause, FilterValue
from pathfinder.domain.strategy.validation import StepValidation
from pathfinder.integrations.veupathdb.client import VEuPathDBClient
from pathfinder.integrations.veupathdb.strategy_api import StrategyAPI
from pathfinder.integrations.veupathdb.wdk_models import (
    WDKColumnDistribution,
    WDKFilterValue,
    WDKSearchConfig,
    WDKStepAnalysisTypeResponse,
)
from pathfinder.platform.errors import WDKError

_SOURCE_ROOT = Path(__file__).resolve().parents[4]
_SCHEMA_LEVELS = frozenset({"NONE", "UNSPECIFIED", "SYNTACTIC", "SEMANTIC", "RUNNABLE"})


class TestWdkFilter001ThreeMechanismsInThreePlaces:
    def test_wdk_filter_001_the_search_config_keeps_them_apart(self) -> None:
        assert {"parameters", "filters", "column_filters"} <= set(
            WDKSearchConfig.model_fields
        )

    def test_wdk_filter_001_a_filter_parameter_lives_among_the_parameters(self) -> None:
        # It is a parameter, so it validates like one and is part of the
        # step's identity.
        value = FilterValue(filters=[FilterTermClause(field="organism")])
        config = WDKSearchConfig(parameters={"organism_filter": value.to_wire()})

        assert (
            json.loads(config.parameters["organism_filter"])["filters"][0]["field"]
            == "organism"
        )

    def test_wdk_filter_001_a_declared_filter_is_a_name_and_a_value(self) -> None:
        config = WDKSearchConfig(
            filters=[WDKFilterValue(name="always_applied", value=None, disabled=False)]
        )

        assert set(config.filters[0].model_dump(by_alias=True)) == {
            "name",
            "value",
            "disabled",
        }

    def test_wdk_filter_001_a_column_filter_is_keyed_by_column_then_tool(self) -> None:
        config = WDKSearchConfig(
            columnFilters={"gene_product": {"byValue": {"pattern": "kinase"}}}
        )

        assert config.column_filters == {
            "gene_product": {"byValue": {"pattern": "kinase"}}
        }

    def test_wdk_filter_001_view_filters_are_a_fourth_name_elsewhere(self) -> None:
        # viewFilters belongs at the top level of a report body, not here.
        config = WDKSearchConfig(
            parameters={"a": "1"},
            filters=[WDKFilterValue(name="f", value=None, disabled=False)],
        )

        assert "viewFilters" not in config.model_dump(
            by_alias=True, exclude_defaults=True
        )


class TestWdkFilter006ByValueIsNotOfferedByTheRecordType:
    @pytest.mark.parametrize("status", [400, 500])
    async def test_wdk_filter_006_a_refusal_is_not_treated_as_a_broken_request(
        self, status: int, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The record-type document advertises byValue on thousands of columns
        # that a step will not accept it on, so a refusal here means "not on
        # this search", not "malformed".
        client = VEuPathDBClient("https://example.invalid/service")
        api = StrategyAPI(client)

        async def get(path: str, **_: object) -> Any:
            del path
            return {"id": 4315616, "isGuest": False}

        async def post(path: str, **_: object) -> Any:
            del path
            msg = 'column "primary_key" does not have have configured filter "byValue"'
            raise WDKError(msg, status=status)

        monkeypatch.setattr(client, "get", get)
        monkeypatch.setattr(client, "post", post)

        result = await api.get_column_distribution(440085983, "primary_key")

        assert result == WDKColumnDistribution()

    async def test_wdk_filter_006_the_distribution_is_asked_of_the_step(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client = VEuPathDBClient("https://example.invalid/service")
        api = StrategyAPI(client)
        paths: list[str] = []

        async def get(path: str, **_: object) -> Any:
            del path
            return {"id": 4315616, "isGuest": False}

        async def post(path: str, **_: object) -> Any:
            paths.append(path)
            return {"histogram": [], "statistics": {}}

        monkeypatch.setattr(client, "get", get)
        monkeypatch.setattr(client, "post", post)

        await api.get_column_distribution(440085983, "gene_product")

        assert paths == [
            "/users/4315616/steps/440085983/columns/gene_product/reports/byValue"
        ]


class TestWdkValid007TheLevelEnumIsNotClosed:
    def test_wdk_valid_007_a_displayable_bundle_parses(self) -> None:
        # The form service builds at a level the step schema does not list.
        bundle = StepValidation.model_validate(
            {"level": "DISPLAYABLE", "isValid": True}
        )

        assert bundle.level == "DISPLAYABLE"
        assert bundle.level not in _SCHEMA_LEVELS

    def test_wdk_valid_007_an_analysis_type_response_carries_it(self) -> None:
        response = WDKStepAnalysisTypeResponse.model_validate(
            {
                "searchData": {"name": "word-enrichment", "displayName": "Words"},
                "validation": {"level": "DISPLAYABLE", "isValid": True},
            }
        )

        assert response.validation.level == "DISPLAYABLE"

    def test_wdk_valid_007_the_level_is_a_string_and_not_an_enum(self) -> None:
        assert StepValidation.model_fields["level"].annotation is str

    def test_wdk_valid_007_an_unchecked_level_still_reads_as_unchecked(self) -> None:
        displayable = StepValidation(level="DISPLAYABLE", is_valid=True)

        assert displayable.was_checked()
        assert not displayable.rejects()

    def test_wdk_valid_007_no_level_is_ever_sent_to_wdk(self) -> None:
        # A level that is legal in the model can be fatal on the way out.
        source_root = _SOURCE_ROOT
        senders = [
            path.relative_to(source_root).as_posix()
            for path in source_root.rglob("*.py")
            if "tests/" not in path.relative_to(source_root).as_posix()
            and "validationLevel" in path.read_text()
        ]

        assert senders == []

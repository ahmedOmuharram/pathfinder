"""set_eda_filters answers with a sheet, then binds what the model proposed."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage
from shared_py.stream_parts.eda import EdaAnalysisState
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.lead.sub_agent_tools import LeadDeps
from pathfinder.ai.tools.standalone import eda_analysis
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.integrations.eda.models import (
    EdaAnalysisDetail,
    EdaFilter,
    EdaPermissionEntry,
    EdaStringSetFilter,
    EdaStudyDetail,
    EdaStudyDetailResponse,
)
from pathfinder.services.eda import binding
from pathfinder.services.eda.authoring import SubsetRejectedError
from pathfinder.services.eda.binding import ConversationAnalysisView
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService

FIXTURES = (
    Path(__file__).resolve().parents[4] / "unit" / "integrations" / "eda" / "fixtures"
)

_DATASET = "DS_53f554ec6a"
_STUDY = "STUDY_53f554ec6a"
_ENTITY = "GENE_PHENOTYPE_DATA_ENTITY"
_SPECIES = "VAR_035294d0"
_ANALYSIS = "t4fszEJ"


def _never_factory() -> AsyncSession:
    msg = "db factory should not be called in unit tests"
    raise AssertionError(msg)


@pytest.fixture
def lead_ctx() -> RunContext[LeadDeps]:
    state = PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
        user_prompt="keep the berghei rows",
    )
    runtime = Context(
        site_id="plasmodb",
        user_id=state.user_id,
        strategy_session=StrategySession(site_id="plasmodb"),
        db_session_factory=_never_factory,
        web_search_service=WebSearchService(),
        literature_search_service=LiteratureSearchService(),
        cancel_event=asyncio.Event(),
    )
    deps = LeadDeps(state=state, intent=None, runtime=runtime, retrieved_memories=[])
    return RunContext(deps=deps, model=TestModel(), usage=RunUsage(), messages=[])


class _Revisions:
    """A counting stand-in for the binding's atomic revision bump."""

    def __init__(self) -> None:
        self.count = 0

    async def bump(self, *, conversation_id: object) -> int:
        del conversation_id
        self.count += 1
        return self.count


@pytest.fixture(autouse=True)
def revisions(monkeypatch: pytest.MonkeyPatch) -> _Revisions:
    counter = _Revisions()
    monkeypatch.setattr(binding, "bump_analysis_revision", counter.bump)
    return counter


def _entry() -> EdaPermissionEntry:
    return EdaPermissionEntry.model_validate(
        {
            "studyId": _STUDY,
            "displayName": "Rodent malaria phenotypes",
            "actionAuthorization": {"subsetting": True, "resultsAll": True},
        }
    )


async def _phenotype_study(
    _site: str,
    _dataset_id: str,
) -> tuple[EdaPermissionEntry, EdaStudyDetail]:
    payload = json.loads((FIXTURES / "study_detail_phenotype.json").read_text())
    return _entry(), EdaStudyDetailResponse.model_validate(payload).study


async def _date_and_number_study(
    _site: str,
    _dataset_id: str,
) -> tuple[EdaPermissionEntry, EdaStudyDetail]:
    variables: list[dict[str, Any]] = [
        {
            "id": "VAR_collected",
            "type": "date",
            "displayName": "Collection date",
            "dataShape": "continuous",
            "distributionDefaults": {
                "rangeMin": "2017-05-05",
                "rangeMax": "2018-01-01",
            },
        },
        {
            "id": "VAR_age",
            "type": "number",
            "displayName": "Age",
            "dataShape": "continuous",
            "distributionDefaults": {"rangeMin": 0.0, "rangeMax": 99.0},
        },
    ]
    study = EdaStudyDetail.model_validate(
        {
            "id": _STUDY,
            "rootEntity": {
                "id": _ENTITY,
                "displayName": "Samples",
                "variables": variables,
            },
        }
    )
    return _entry(), study


async def _longitude_study(
    _site: str,
    _dataset_id: str,
) -> tuple[EdaPermissionEntry, EdaStudyDetail]:
    variables: list[dict[str, Any]] = [
        {
            "id": "VAR_lon",
            "type": "longitude",
            "displayName": "Collection longitude",
            "dataShape": "continuous",
            "distributionDefaults": {"rangeMin": -12.5, "rangeMax": 41.0},
        },
        {
            "id": "VAR_lat",
            "type": "number",
            "displayName": "Collection latitude",
            "dataShape": "continuous",
            "distributionDefaults": {"rangeMin": -8.0, "rangeMax": 15.0},
        },
    ]
    study = EdaStudyDetail.model_validate(
        {
            "id": _STUDY,
            "rootEntity": {
                "id": _ENTITY,
                "displayName": "Samples",
                "variables": variables,
            },
        }
    )
    return _entry(), study


async def _bound(_ctx: object) -> ConversationAnalysisView:
    return ConversationAnalysisView(
        site_id="plasmodb",
        dataset_id=_DATASET,
        analysis_id=_ANALYSIS,
        revision=1,
    )


async def _unbound(_ctx: object) -> ConversationAnalysisView | None:
    return None


def _species_filter(value: str) -> EdaStringSetFilter:
    return EdaStringSetFilter(
        entity_id=_ENTITY, variable_id=_SPECIES, string_set=[value]
    )


def _detail(*, num_filters: int) -> EdaAnalysisDetail:
    descriptor: list[dict[str, Any]] = (
        [
            {
                "entityId": _ENTITY,
                "variableId": _SPECIES,
                "type": "stringSet",
                "stringSet": ["P. berghei"],
            }
        ]
        if num_filters
        else []
    )
    return EdaAnalysisDetail.model_validate(
        {
            "analysisId": _ANALYSIS,
            "displayName": "berghei subset",
            "studyId": _DATASET,
            "numFilters": num_filters,
            "numComputations": 0,
            "descriptor": {"subset": {"descriptor": descriptor}},
        }
    )


def _state(*, num_filters: int) -> EdaAnalysisState:
    return EdaAnalysisState(
        site_id="plasmodb",
        dataset_id=_DATASET,
        study_id=_STUDY,
        analysis_id=_ANALYSIS,
        revision=1,
        study_display_name="Rodent malaria phenotypes",
        display_name="berghei subset",
        num_filters=num_filters,
        num_computations=0,
        filters=[],
        filter_summaries=(["Species is one of P. berghei"] if num_filters else []),
        entity_counts=[],
        can_export_rows=False,
    )


async def _apply_ok(
    _site: str,
    *,
    conversation_id: UUID,
    analysis_id: str,
    dataset_id: str,
    filters: Sequence[EdaFilter],
) -> EdaAnalysisState:
    del conversation_id
    assert analysis_id == _ANALYSIS
    assert dataset_id == _DATASET
    assert len(filters) == 1
    return _state(num_filters=1)


async def _apply_cleared(
    _site: str,
    *,
    conversation_id: UUID,
    analysis_id: str,
    dataset_id: str,
    filters: Sequence[EdaFilter],
) -> EdaAnalysisState:
    del conversation_id, analysis_id, dataset_id
    assert filters == []
    return _state(num_filters=0)


async def _apply_rejects(
    _site: str,
    *,
    conversation_id: UUID,
    analysis_id: str,
    dataset_id: str,
    filters: Sequence[EdaFilter],
) -> EdaAnalysisState:
    raise SubsetRejectedError(
        [
            f"Filter stringSet on variable {_SPECIES} of entity {_ENTITY} names "
            f"P. vivax, which the vocabulary does not carry. The vocabulary is "
            f"P. berghei, P. falciparum, P. yoelii."
        ]
    )


async def test_a_first_call_with_no_filters_returns_the_sheet(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    monkeypatch.setattr(eda_analysis, "get_study_detail_for_dataset", _phenotype_study)
    monkeypatch.setattr(eda_analysis, "bound_analysis", _bound)
    returned = await eda_analysis.set_eda_filters(lead_ctx, dataset_id=_DATASET)
    result = returned.return_value
    assert result.decide
    assert result.applied is False


async def test_the_sheet_names_the_exact_filter_type_per_variable(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    monkeypatch.setattr(eda_analysis, "get_study_detail_for_dataset", _phenotype_study)
    monkeypatch.setattr(eda_analysis, "bound_analysis", _bound)
    returned = await eda_analysis.set_eda_filters(lead_ctx, dataset_id=_DATASET)
    result = returned.return_value
    species = next(e for e in result.decide if e.variable_id == _SPECIES)
    assert species.filter_type == "stringSet"
    assert species.example == {
        "entityId": _ENTITY,
        "variableId": _SPECIES,
        "type": "stringSet",
        "stringSet": ["P. berghei"],
    }
    assert species.entity_display_name == "Gene Phenotype Data"


async def test_a_date_example_carries_the_time_part_the_service_requires(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    """A bare YYYY-MM-DD bound is a server error, so the example never shows one."""
    monkeypatch.setattr(
        eda_analysis, "get_study_detail_for_dataset", _date_and_number_study
    )
    monkeypatch.setattr(eda_analysis, "bound_analysis", _bound)
    returned = await eda_analysis.set_eda_filters(lead_ctx, dataset_id=_DATASET)
    result = returned.return_value
    collected = next(e for e in result.decide if e.variable_id == "VAR_collected")
    assert collected.filter_type == "dateRange"
    assert collected.date_min == "2017-05-05T00:00:00"
    assert collected.example["min"] == "2017-05-05T00:00:00"
    age = next(e for e in result.decide if e.variable_id == "VAR_age")
    assert age.filter_type == "numberRange"
    assert age.example == {
        "entityId": _ENTITY,
        "variableId": "VAR_age",
        "type": "numberRange",
        "min": 0.0,
        "max": 99.0,
    }


async def test_a_longitude_variable_is_not_a_number_variable(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    """A longitude takes left and right, so a numberRange on it selects wrongly."""
    monkeypatch.setattr(eda_analysis, "get_study_detail_for_dataset", _longitude_study)
    monkeypatch.setattr(eda_analysis, "bound_analysis", _bound)
    returned = await eda_analysis.set_eda_filters(lead_ctx, dataset_id=_DATASET)
    result = returned.return_value
    longitude = next(e for e in result.decide if e.variable_id == "VAR_lon")
    assert longitude.filter_type == "longitudeRange"
    assert longitude.example == {
        "entityId": _ENTITY,
        "variableId": "VAR_lon",
        "type": "longitudeRange",
        "left": -180.0,
        "right": 180.0,
    }
    latitude = next(e for e in result.decide if e.variable_id == "VAR_lat")
    assert latitude.filter_type == "numberRange"
    assert latitude.example["min"] == -8.0
    assert latitude.example["max"] == 15.0


async def test_a_second_call_applies_the_filters_and_emits_the_state(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    monkeypatch.setattr(eda_analysis, "get_study_detail_for_dataset", _phenotype_study)
    monkeypatch.setattr(eda_analysis, "bound_analysis", _bound)
    monkeypatch.setattr(eda_analysis, "apply_filters", _apply_ok)
    returned = await eda_analysis.set_eda_filters(
        lead_ctx,
        dataset_id=_DATASET,
        filters=[_species_filter("P. berghei")],
    )
    assert returned.return_value.applied is True
    assert returned.return_value.num_filters == 1
    assert returned.return_value.filter_summaries == [
        "Species is one of P. berghei",
    ]
    assert [c.type for c in returned.metadata] == ["data-eda.analysis-state"]
    assert returned.metadata[0].data["revision"] == 1


async def test_an_out_of_vocabulary_value_raises_a_model_retry_with_the_options(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    """The service would answer 200 with count 0, so the retry is the only signal."""
    monkeypatch.setattr(eda_analysis, "get_study_detail_for_dataset", _phenotype_study)
    monkeypatch.setattr(eda_analysis, "bound_analysis", _bound)
    monkeypatch.setattr(eda_analysis, "apply_filters", _apply_rejects)
    with pytest.raises(ModelRetry) as excinfo:
        await eda_analysis.set_eda_filters(
            lead_ctx,
            dataset_id=_DATASET,
            filters=[_species_filter("P. vivax")],
        )
    message = str(excinfo.value)
    assert "P. vivax" in message
    assert "P. berghei" in message
    assert "do not request the sheet again" in message


async def test_calling_with_no_open_analysis_raises_a_model_retry_naming_the_tool(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    monkeypatch.setattr(eda_analysis, "bound_analysis", _unbound)
    with pytest.raises(ModelRetry) as excinfo:
        await eda_analysis.set_eda_filters(
            lead_ctx, dataset_id=_DATASET, filters=[_species_filter("P. berghei")]
        )
    assert "open_eda_analysis" in str(excinfo.value)


async def test_a_dataset_other_than_the_open_one_raises_a_model_retry(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    """One conversation edits one analysis, so the argument must name it."""
    monkeypatch.setattr(eda_analysis, "bound_analysis", _bound)
    with pytest.raises(ModelRetry) as excinfo:
        await eda_analysis.set_eda_filters(
            lead_ctx,
            dataset_id="DS_eeca6a5476",
            filters=[_species_filter("P. berghei")],
        )
    assert _DATASET in str(excinfo.value)


async def test_the_second_sheet_for_the_same_study_omits_the_vocabularies(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    """The model already holds them; resending costs the whole prompt cache."""
    monkeypatch.setattr(eda_analysis, "get_study_detail_for_dataset", _phenotype_study)
    monkeypatch.setattr(eda_analysis, "bound_analysis", _bound)
    first = (
        await eda_analysis.set_eda_filters(lead_ctx, dataset_id=_DATASET)
    ).return_value
    second = (
        await eda_analysis.set_eda_filters(lead_ctx, dataset_id=_DATASET)
    ).return_value
    assert any(e.vocabulary for e in first.decide)
    assert all(e.vocabulary == [] for e in second.decide)
    assert all(e.vocabulary_note for e in second.decide if e.vocabulary_total)


async def test_an_empty_filter_list_clears_the_subset(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    """An analysis with no filters is legal and means the whole study."""
    monkeypatch.setattr(eda_analysis, "get_study_detail_for_dataset", _phenotype_study)
    monkeypatch.setattr(eda_analysis, "bound_analysis", _bound)
    monkeypatch.setattr(eda_analysis, "apply_filters", _apply_cleared)
    returned = await eda_analysis.set_eda_filters(
        lead_ctx, dataset_id=_DATASET, filters=[]
    )
    assert returned.return_value.applied is True
    assert returned.return_value.num_filters == 0

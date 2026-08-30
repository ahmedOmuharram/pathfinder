"""The EDA tools, the chunks they emit, and the retries they raise."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from assistant_core.persistence.models import Conversation
from assistant_core.platform.db import async_session_factory
from pydantic import ValidationError
from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.models.test import TestModel
from pydantic_ai.ui.vercel_ai.response_types import DataChunk
from pydantic_ai.usage import RunUsage
from shared_py.stream_parts.eda import EdaEntityCount, EdaVolcanoPoint
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.lead.sub_agent_tools import LeadDeps
from pathfinder.ai.tools.standalone import eda_analysis, eda_catalog
from pathfinder.ai.tools.standalone._eda_stream_parts import (
    eda_analysis_state_chunk,
    eda_subset_preview_chunk,
    eda_viz_chunk,
)
from pathfinder.domain.eda import walk_entities
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.integrations.eda import factory as eda_factory
from pathfinder.integrations.eda.client import EdaClient
from pathfinder.integrations.eda.models import (
    EdaAnalysisDetail,
    EdaDistributionResponse,
    EdaFilter,
    EdaPermissionEntry,
    EdaStringSetFilter,
    EdaStudyDetail,
    EdaStudyDetailResponse,
)
from pathfinder.persistence.models import User
from pathfinder.platform.context import veupathdb_auth_token_ctx
from pathfinder.services.eda import authoring, binding, catalog
from pathfinder.services.eda.authoring import SubsetPreview
from pathfinder.services.eda.binding import ConversationAnalysisView
from pathfinder.services.eda.catalog import (
    NAME_MATCH_GUIDANCE,
    StudyCard,
    StudySearch,
    UnknownEdaDatasetError,
)
from pathfinder.services.eda.compute import RetainedSummary
from pathfinder.services.eda.description import permission_facts
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService

FIXTURES = (
    Path(__file__).resolve().parents[2] / "unit" / "integrations" / "eda" / "fixtures"
)

_DATASET = "DS_53f554ec6a"
_STUDY = "STUDY_53f554ec6a"
_ENTITY = "GENE_PHENOTYPE_DATA_ENTITY"


def _fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


def _never_factory() -> AsyncSession:
    msg = "db factory should not be called in these tests"
    raise AssertionError(msg)


@pytest.fixture
def lead_ctx() -> RunContext[LeadDeps]:
    state = PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
        user_prompt="look at the rodent malaria phenotypes",
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


async def _entity_counts(
    _site: str,
    *,
    study: EdaStudyDetail,
    filters: Sequence[EdaFilter],
) -> list[EdaEntityCount]:
    """The recorded phenotype pair, for every entity the study declares."""
    del filters
    return [
        EdaEntityCount(
            entity_id=entity.id,
            entity_display_name=entity.display_name,
            count=4011,
            unfiltered_count=4279,
        )
        for entity in walk_entities(study.root_entity)
    ]


@pytest.fixture(autouse=True)
def entity_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    """These tools are read through their chunks, not through the count wire."""
    monkeypatch.setattr(binding, "subset_entity_counts", _entity_counts)


def _entry(*, results_all: bool = True) -> EdaPermissionEntry:
    return EdaPermissionEntry.model_validate(
        {
            "studyId": _STUDY,
            "displayName": "Rodent malaria phenotypes",
            "actionAuthorization": {
                "studyMetadata": True,
                "subsetting": True,
                "resultsAll": results_all,
            },
        }
    )


async def _phenotype_study(
    _site: str,
    _dataset_id: str,
) -> tuple[EdaPermissionEntry, EdaStudyDetail]:
    detail = EdaStudyDetailResponse.model_validate(
        _fixture("study_detail_phenotype.json")
    ).study
    return _entry(), detail


def _study_of(variables: list[dict[str, Any]], *, entity_id: str) -> EdaStudyDetail:
    return EdaStudyDetail.model_validate(
        {
            "id": _STUDY,
            "rootEntity": {
                "id": entity_id,
                "displayName": entity_id,
                "displayNamePlural": entity_id,
                "variables": variables,
            },
        }
    )


async def _wide_vocabulary_study(
    _site: str,
    _dataset_id: str,
) -> tuple[EdaPermissionEntry, EdaStudyDetail]:
    wide = {
        "id": "VAR_wide",
        "type": "string",
        "displayName": "Sample id",
        "dataShape": "categorical",
        "isMultiValued": False,
        "vocabulary": [f"term-{index}" for index in range(500)],
    }
    return _entry(), _study_of([wide], entity_id="E")


async def _multifilter_study(
    _site: str,
    _dataset_id: str,
) -> tuple[EdaPermissionEntry, EdaStudyDetail]:
    category = {
        "id": "VAR_category",
        "type": "category",
        "displayName": "Assay results",
        "displayType": "multifilter",
    }
    children = [
        {
            "id": f"VAR_child_{index}",
            "type": "string",
            "displayName": f"Child {index}",
            "parentId": "VAR_category",
            "dataShape": "categorical",
            "vocabulary": ["yes", "no"],
        }
        for index in range(2)
    ]
    return _entry(), _study_of([category, *children], entity_id="EUPATH_0000096")


async def _no_gene_study(
    _site: str,
    _dataset_id: str,
) -> tuple[EdaPermissionEntry, EdaStudyDetail]:
    sample = {
        "id": "VAR_sample",
        "type": "string",
        "displayName": "Sample",
        "dataShape": "categorical",
        "vocabulary": ["a", "b"],
    }
    return _entry(results_all=False), _study_of([sample], entity_id="E")


async def _bound(_ctx: object) -> ConversationAnalysisView:
    return ConversationAnalysisView(
        site_id="plasmodb",
        dataset_id=_DATASET,
        analysis_id="t4fszEJ",
        revision=1,
    )


async def _unbound(_ctx: object) -> ConversationAnalysisView | None:
    return None


def _preview(
    *,
    count: int,
    distribution: EdaDistributionResponse | None,
) -> SubsetPreview:
    return SubsetPreview(
        entity_id=_ENTITY,
        entity_display_name="Gene Phenotype Data",
        count=count,
        unfiltered_count=4279,
        distribution=distribution,
    )


def _categorical() -> EdaDistributionResponse:
    return EdaDistributionResponse.model_validate(
        _fixture("distribution_categorical.json")
    )


async def _preview_ok(_site: str, **_kwargs: object) -> SubsetPreview:
    return _preview(count=4011, distribution=_categorical())


async def _preview_zero(_site: str, **_kwargs: object) -> SubsetPreview:
    return _preview(count=0, distribution=None)


async def _preview_whole_entity(_site: str, **_kwargs: object) -> SubsetPreview:
    return _preview(count=4279, distribution=None)


async def _preview_with_missing(_site: str, **_kwargs: object) -> SubsetPreview:
    payload = _fixture("distribution_categorical.json")
    payload["statistics"]["numMissingCases"] = 12
    return _preview(
        count=4011, distribution=EdaDistributionResponse.model_validate(payload)
    )


async def _resolved(value: str) -> str:
    return value


async def _read_detail(_site: str, *, analysis_id: str) -> EdaAnalysisDetail:
    return _detail()


async def _noop_bind(**_kwargs: object) -> None:
    return None


def _detail() -> EdaAnalysisDetail:
    return EdaAnalysisDetail.model_validate(
        {
            "analysisId": "t4fszEJ",
            "displayName": "berghei subset",
            "studyId": _DATASET,
            "numFilters": 1,
            "numComputations": 0,
            "descriptor": {
                "subset": {
                    "descriptor": [
                        {
                            "entityId": _ENTITY,
                            "variableId": "VAR_035294d0",
                            "type": "stringSet",
                            "stringSet": ["P. berghei"],
                        }
                    ],
                    "uiSettings": {},
                },
                "computations": [],
                "starredVariables": [],
                "dataTableConfig": {},
                "derivedVariables": [],
            },
        }
    )


async def test_the_analysis_state_chunk_names_the_part_kind() -> None:
    entry, study = await _phenotype_study("plasmodb", _DATASET)
    chunk = eda_analysis_state_chunk(
        await binding.analysis_state(
            site_id="plasmodb",
            dataset_id=_DATASET,
            entry=permission_facts(entry),
            study=study,
            analysis=_detail(),
            revision=3,
        )
    )
    assert chunk.type == "data-eda.analysis-state"
    assert chunk.data["analysisId"] == "t4fszEJ"
    assert chunk.data["numFilters"] == 1
    assert chunk.data["revision"] == 3
    assert chunk.data["filterSummaries"] == ["Species is one of P. berghei"]
    assert chunk.data["entityCounts"] == [
        {
            "entityId": _ENTITY,
            "entityDisplayName": "Gene Phenotype Data",
            "count": 4011,
            "unfilteredCount": 4279,
        }
    ]
    assert chunk.data["filters"] == [
        {
            "entityId": _ENTITY,
            "variableId": "VAR_035294d0",
            "type": "stringSet",
            "stringSet": ["P. berghei"],
        }
    ]


def test_the_subset_preview_chunk_converts_a_histogram_to_a_series() -> None:
    preview = SubsetPreview(
        entity_id=_ENTITY,
        entity_display_name="Gene phenotype",
        count=4011,
        unfiltered_count=4279,
        distribution=EdaDistributionResponse.model_validate(
            _fixture("distribution_categorical.json")
        ),
    )
    chunk = eda_subset_preview_chunk(
        dataset_id=_DATASET,
        analysis_id="t4fszEJ",
        preview=preview,
        variable_id="VAR_035294d0",
        variable_display_name="Species",
        is_multi_valued=True,
    )
    assert chunk.type == "data-eda.subset-preview"
    counts = chunk.data["entityCounts"]
    assert counts[0]["count"] == 4011
    assert counts[0]["unfilteredCount"] == 4279
    assert counts[0]["entityDisplayName"] == "Gene phenotype"
    series = chunk.data["distribution"]
    assert series["labels"] == ["P. berghei", "P. falciparum", "P. yoelii"]
    assert series["values"] == [4011.0, 4130.0, 268.0]
    assert series["isMultiValued"] is True
    assert series["numVarValues"] == 8409
    assert series["subsetSize"] == 4279


def test_the_subset_preview_chunk_omits_the_series_when_there_is_none() -> None:
    preview = SubsetPreview(
        entity_id=_ENTITY,
        entity_display_name="Gene phenotype",
        count=4011,
        unfiltered_count=4279,
        distribution=None,
        distribution_note="Variable VAR_x is continuous and declares no binWidth.",
    )
    chunk = eda_subset_preview_chunk(
        dataset_id=_DATASET,
        analysis_id="t4fszEJ",
        preview=preview,
        variable_id=None,
        variable_display_name="",
        is_multi_valued=False,
    )
    assert chunk.data["distribution"] is None
    assert chunk.data["distributionNote"] == (
        "Variable VAR_x is continuous and declares no binWidth."
    )


def _point(index: int, *, retained: bool) -> EdaVolcanoPoint:
    return EdaVolcanoPoint(
        point_id=f"PF3D7_{index:07d}",
        effect_size=2.0 if retained else 0.1,
        p_value=0.001,
        adjusted_p_value=0.01,
        retained=retained,
    )


def test_the_viz_chunk_reports_the_measured_totals() -> None:
    chunk = eda_viz_chunk(
        dataset_id="DS_e973eadd57",
        analysis_id="t4fszEJ",
        effect_size_label="log2(Fold Change)",
        effect_size_threshold=1.0,
        significance_threshold=0.05,
        effect_direction="upAndDown",
        summary=RetainedSummary(
            total_rows=5511,
            unparseable_rows=1,
            retained=1543,
            retained_up=800,
            retained_down=743,
        ),
        points=[_point(1, retained=True)],
    )
    assert chunk.type == "data-eda.viz"
    assert chunk.data["chart"] == "volcano"
    assert chunk.data["totalPoints"] == 5511
    assert chunk.data["retainedPoints"] == 1543
    assert chunk.data["effectDirection"] == "upAndDown"


def test_the_viz_chunk_refuses_a_direction_no_chart_draws() -> None:
    with pytest.raises(ValidationError):
        eda_viz_chunk(
            dataset_id="DS_e973eadd57",
            analysis_id="t4fszEJ",
            effect_size_label="log2(Fold Change)",
            effect_size_threshold=1.0,
            significance_threshold=0.05,
            effect_direction="sideways",
            summary=RetainedSummary(
                total_rows=1,
                unparseable_rows=0,
                retained=0,
                retained_up=0,
                retained_down=0,
            ),
            points=[],
        )


def test_the_viz_chunk_caps_the_points_and_keeps_every_retained_one() -> None:
    """The cap is below the measured 5511 rows, so the order decides who survives."""
    points = [_point(i, retained=False) for i in range(4500)]
    points.extend(_point(9000 + i, retained=True) for i in range(20))
    chunk = eda_viz_chunk(
        dataset_id="DS_e973eadd57",
        analysis_id="t4fszEJ",
        effect_size_label="log2(Fold Change)",
        effect_size_threshold=1.0,
        significance_threshold=0.05,
        effect_direction="upAndDown",
        summary=RetainedSummary(
            total_rows=4520,
            unparseable_rows=0,
            retained=20,
            retained_up=20,
            retained_down=0,
        ),
        points=points,
    )
    sent = chunk.data["points"]
    assert len(sent) == 4000
    assert sum(1 for point in sent if point["retained"]) == 20


async def test_search_eda_studies_returns_cards_the_model_can_act_on(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    async def cards(_site: str, _query: str, limit: int = 5) -> list[StudyCard]:
        return [
            StudyCard(
                dataset_id=_DATASET,
                study_id=_STUDY,
                display_name="Rodent malaria phenotypes",
                short_display_name="Rod Mal Phenotype",
                description="Phenotypes of genetically modified rodent malaria",
                source_type="curated",
                relevance=0.71,
                can_subset=True,
                can_export_rows=True,
            )
        ][:limit]

    async def found(_site: str, _query: str, limit: int = 5) -> StudySearch:
        return StudySearch(cards=await cards(_site, _query, limit))

    monkeypatch.setattr(eda_catalog, "search_studies", found)
    result = (
        await eda_catalog.search_eda_studies(lead_ctx, query="rodent malaria")
    ).return_value
    assert result.studies
    first = result.studies[0]
    assert first.dataset_id == _DATASET
    assert first.study_id == _STUDY
    assert first.can_export_rows is True
    assert "Phenotypes" in first.description
    assert "describe_eda_study" in result.guidance


async def test_search_eda_studies_says_so_when_nothing_matches(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    async def none(_site: str, _query: str, limit: int = 5) -> StudySearch:
        del limit
        return StudySearch(cards=[])

    monkeypatch.setattr(eda_catalog, "search_studies", none)
    result = (
        await eda_catalog.search_eda_studies(lead_ctx, query="nothing here")
    ).return_value
    assert result.studies == []
    assert "No EDA study" in result.guidance


async def test_describe_eda_study_reports_the_entity_tree_and_the_gene_entity(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    monkeypatch.setattr(eda_catalog, "get_study_detail_for_dataset", _phenotype_study)
    result = (
        await eda_catalog.describe_eda_study(lead_ctx, dataset_id=_DATASET)
    ).return_value
    assert result.study_id == _STUDY
    assert result.gene_entity_id == _ENTITY
    entities = {e.entity_id: e for e in result.entities}
    assert _ENTITY in entities
    assert entities[_ENTITY].variable_count > 0
    assert entities[_ENTITY].has_gene_id is True
    assert result.variables == []


async def test_describe_eda_study_summarises_a_vocabulary_without_dumping_it(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    """A tool payload must fit a context window; 4000 terms must not travel."""
    monkeypatch.setattr(eda_catalog, "get_study_detail_for_dataset", _phenotype_study)
    result = (
        await eda_catalog.describe_eda_study(
            lead_ctx, dataset_id=_DATASET, entity_id=_ENTITY
        )
    ).return_value
    species = next(v for v in result.variables if v.variable_id == "VAR_035294d0")
    assert species.vocabulary_total == 3
    assert species.vocabulary == ["P. berghei", "P. falciparum", "P. yoelii"]
    assert species.is_multi_valued is True
    assert species.filter_type == "stringSet"
    assert species.entity_id == _ENTITY


async def _hidden_everywhere_study(
    _site: str,
    _dataset_id: str,
) -> tuple[EdaPermissionEntry, EdaStudyDetail]:
    hidden = {
        "id": "VAR_hidden",
        "type": "string",
        "displayName": "Internal batch",
        "dataShape": "categorical",
        "vocabulary": ["batch-1", "batch-2"],
        "hideFrom": ["everywhere"],
    }
    return _entry(), _study_of([hidden], entity_id=_ENTITY)


async def test_describe_eda_study_lists_a_variable_the_site_hides_everywhere(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    """hideFrom is UI advice, not access control; the variable is still filterable."""
    monkeypatch.setattr(
        eda_catalog, "get_study_detail_for_dataset", _hidden_everywhere_study
    )
    result = (
        await eda_catalog.describe_eda_study(
            lead_ctx, dataset_id=_DATASET, entity_id=_ENTITY
        )
    ).return_value
    hidden = next(v for v in result.variables if v.variable_id == "VAR_hidden")
    assert hidden.filter_type == "stringSet"
    assert hidden.vocabulary == ["batch-1", "batch-2"]


async def test_describe_eda_study_truncates_a_long_vocabulary_and_says_so(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    monkeypatch.setattr(
        eda_catalog, "get_study_detail_for_dataset", _wide_vocabulary_study
    )
    result = (
        await eda_catalog.describe_eda_study(
            lead_ctx, dataset_id=_DATASET, entity_id="E"
        )
    ).return_value
    wide = result.variables[0]
    assert wide.vocabulary_total == 500
    assert len(wide.vocabulary) == 40
    assert wide.vocabulary_note is not None
    assert "500" in wide.vocabulary_note


async def test_describe_eda_study_names_a_multifilter_category_and_its_children(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    monkeypatch.setattr(eda_catalog, "get_study_detail_for_dataset", _multifilter_study)
    result = (
        await eda_catalog.describe_eda_study(
            lead_ctx, dataset_id=_DATASET, entity_id="EUPATH_0000096"
        )
    ).return_value
    category = next(v for v in result.variables if v.filter_type == "multiFilter")
    assert category.sub_filter_variable_ids == ["VAR_child_0", "VAR_child_1"]
    assert category.vocabulary == []


async def test_describe_eda_study_refuses_a_study_with_no_gene_id_variable(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    monkeypatch.setattr(eda_catalog, "get_study_detail_for_dataset", _no_gene_study)
    result = (
        await eda_catalog.describe_eda_study(lead_ctx, dataset_id=_DATASET)
    ).return_value
    assert result.gene_entity_id is None
    assert result.gene_entity_problem is not None
    assert "VEUPATHDB_GENE_ID" in result.gene_entity_problem


async def test_an_unknown_dataset_id_raises_a_model_retry_naming_the_tool(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    async def raises(
        _site: str, _dataset_id: str
    ) -> tuple[EdaPermissionEntry, EdaStudyDetail]:
        unknown = "DS_nope"
        raise UnknownEdaDatasetError(unknown, ["DS_a", "DS_b"])

    monkeypatch.setattr(eda_catalog, "get_study_detail_for_dataset", raises)
    with pytest.raises(ModelRetry) as excinfo:
        await eda_catalog.describe_eda_study(lead_ctx, dataset_id="DS_nope")
    assert "DS_nope" in str(excinfo.value)
    assert "search_eda_studies" in str(excinfo.value)


async def test_open_eda_analysis_creates_the_analysis_and_binds_the_conversation(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    bound: list[tuple[str, str, str]] = []

    async def open_it(_site: str, *, dataset_id: str, display_name: str) -> str:
        assert display_name
        assert dataset_id == _DATASET
        return "t4fszEJ"

    async def bind(**kwargs: object) -> None:
        bound.append(
            (
                str(kwargs["dataset_id"]),
                str(kwargs["analysis_id"]),
                str(kwargs["site_id"]),
            )
        )

    monkeypatch.setattr(binding, "open_analysis", open_it)
    monkeypatch.setattr(binding, "bind_conversation_analysis", bind)
    monkeypatch.setattr(binding, "read_analysis", _read_detail)
    monkeypatch.setattr(eda_analysis, "get_study_detail_for_dataset", _phenotype_study)
    monkeypatch.setattr(binding, "get_study_detail_for_dataset", _phenotype_study)

    returned = await eda_analysis.open_eda_analysis(
        lead_ctx, dataset_id=_DATASET, purpose="keep the P. berghei rows"
    )
    assert returned.return_value.analysis_id == "t4fszEJ"
    assert returned.return_value.study_id == _STUDY
    assert returned.return_value.gene_entity_id == _ENTITY
    assert bound == [(_DATASET, "t4fszEJ", "plasmodb")]
    kinds = [chunk.type for chunk in returned.metadata]
    assert kinds == ["data-eda.analysis-state"]
    assert returned.metadata[0].data["revision"] == 1


async def _fake_user_id(_site_id: str) -> str:
    return "1216062453"


async def test_open_eda_analysis_cuts_a_long_purpose_before_the_wire(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    """The user service refuses a displayName over 50 UTF-8 bytes."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.endswith("/permissions"):
            return httpx.Response(200, json=_fixture("permissions.json"))
        if "/analyses/" in request.url.path and request.method == "POST":
            return httpx.Response(200, json={"analysisId": "t4fszEJ"})
        return httpx.Response(404, json={"status": "not-found"})

    catalog.clear_study_caches()
    client = EdaClient(base_url="https://plasmodb.org/eda")
    client.install_transport(httpx.MockTransport(handler))
    monkeypatch.setattr(catalog, "get_eda_client", lambda _s: client)
    monkeypatch.setattr(authoring, "get_eda_client", lambda _s: client)
    monkeypatch.setattr(eda_factory, "get_eda_client", lambda _s: client)
    monkeypatch.setattr(authoring, "resolve_eda_user_id", _fake_user_id)
    monkeypatch.setattr(binding, "bind_conversation_analysis", _noop_bind)
    monkeypatch.setattr(binding, "read_analysis", _read_detail)
    monkeypatch.setattr(eda_analysis, "get_study_detail_for_dataset", _phenotype_study)
    monkeypatch.setattr(binding, "get_study_detail_for_dataset", _phenotype_study)

    purpose = (
        "Febrile versus normal differential expression in the LRR5 and DHC "
        "heat-shock RNA-seq study"
    )
    assert len(purpose) == 90
    token = veupathdb_auth_token_ctx.set("t")
    try:
        returned = await eda_analysis.open_eda_analysis(
            lead_ctx, dataset_id="DS_16bc228c8e", purpose=purpose
        )
    finally:
        veupathdb_auth_token_ctx.reset(token)
        await client.close()

    assert returned.return_value.analysis_id == "t4fszEJ"
    posts = [r for r in seen if r.method == "POST" and "/analyses/" in r.url.path]
    sent = json.loads(posts[0].content)["displayName"]
    assert sent == "Febrile versus normal differential expression in t"
    assert len(sent.encode()) == 50


async def test_opening_a_second_analysis_replaces_the_binding(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    """One conversation binds at most one open analysis at a time."""
    calls: list[str] = []

    async def bind(**kwargs: object) -> None:
        calls.append(str(kwargs["analysis_id"]))

    monkeypatch.setattr(binding, "bind_conversation_analysis", bind)
    monkeypatch.setattr(binding, "open_analysis", lambda *_a, **_k: _resolved("A"))
    monkeypatch.setattr(binding, "read_analysis", _read_detail)
    monkeypatch.setattr(eda_analysis, "get_study_detail_for_dataset", _phenotype_study)
    monkeypatch.setattr(binding, "get_study_detail_for_dataset", _phenotype_study)
    await eda_analysis.open_eda_analysis(lead_ctx, dataset_id=_DATASET, purpose="first")
    monkeypatch.setattr(binding, "open_analysis", lambda *_a, **_k: _resolved("B"))
    await eda_analysis.open_eda_analysis(
        lead_ctx, dataset_id=_DATASET, purpose="second"
    )
    assert calls == ["A", "B"]


async def test_opening_an_analysis_on_a_study_with_no_gene_id_warns_the_model(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    """A study with no gene column can be explored and cannot be exported."""
    monkeypatch.setattr(binding, "open_analysis", lambda *_a, **_k: _resolved("A"))
    monkeypatch.setattr(binding, "read_analysis", _read_detail)
    monkeypatch.setattr(binding, "bind_conversation_analysis", _noop_bind)
    monkeypatch.setattr(eda_analysis, "get_study_detail_for_dataset", _no_gene_study)
    monkeypatch.setattr(binding, "get_study_detail_for_dataset", _no_gene_study)

    returned = await eda_analysis.open_eda_analysis(
        lead_ctx, dataset_id=_DATASET, purpose="explore"
    )
    assert "cannot export" in returned.return_value.guidance
    assert returned.return_value.can_export_rows is False


async def test_opening_an_analysis_on_an_unknown_dataset_creates_nothing(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    """The study resolves first, so a bad id never leaves an orphan analysis."""
    opened: list[str] = []

    async def raises(
        _site: str, _dataset_id: str
    ) -> tuple[EdaPermissionEntry, EdaStudyDetail]:
        unknown = "DS_nope"
        raise UnknownEdaDatasetError(unknown, ["DS_a"])

    async def open_it(_site: str, **_kwargs: object) -> str:
        opened.append("opened")
        return "A"

    monkeypatch.setattr(eda_analysis, "get_study_detail_for_dataset", raises)
    monkeypatch.setattr(binding, "open_analysis", open_it)
    monkeypatch.setattr(binding, "bind_conversation_analysis", _noop_bind)
    with pytest.raises(ModelRetry) as excinfo:
        await eda_analysis.open_eda_analysis(
            lead_ctx, dataset_id="DS_nope", purpose="explore"
        )
    assert "search_eda_studies" in str(excinfo.value)
    assert opened == []


async def test_preview_eda_subset_reports_both_counts_and_emits_the_part(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    monkeypatch.setattr(eda_analysis, "bound_analysis", _bound)
    monkeypatch.setattr(eda_analysis, "read_analysis", _read_detail)
    monkeypatch.setattr(eda_analysis, "preview_subset", _preview_ok)
    monkeypatch.setattr(eda_analysis, "get_study_detail_for_dataset", _phenotype_study)
    returned = await eda_analysis.preview_eda_subset(
        lead_ctx,
        entity_id=_ENTITY,
        distribution_variable_id="VAR_035294d0",
    )
    assert returned.return_value.count == 4011
    assert returned.return_value.unfiltered_count == 4279
    assert returned.return_value.labels == [
        "P. berghei",
        "P. falciparum",
        "P. yoelii",
    ]
    assert returned.return_value.values == [4011.0, 4130.0, 268.0]
    assert [c.type for c in returned.metadata] == ["data-eda.subset-preview"]


async def test_a_preview_of_zero_says_which_filter_emptied_the_subset(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    """Zero is a real answer and the model must not silently narrate a result."""
    monkeypatch.setattr(eda_analysis, "bound_analysis", _bound)
    monkeypatch.setattr(eda_analysis, "read_analysis", _read_detail)
    monkeypatch.setattr(eda_analysis, "preview_subset", _preview_zero)
    monkeypatch.setattr(eda_analysis, "get_study_detail_for_dataset", _phenotype_study)
    returned = await eda_analysis.preview_eda_subset(lead_ctx, entity_id=_ENTITY)
    assert returned.return_value.count == 0
    assert "selects no records" in returned.return_value.guidance


async def test_a_preview_of_zero_reports_its_summary_as_empty(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    """The line carries the zero and the status says empty, never ok."""
    monkeypatch.setattr(eda_analysis, "bound_analysis", _bound)
    monkeypatch.setattr(eda_analysis, "read_analysis", _read_detail)
    monkeypatch.setattr(eda_analysis, "preview_subset", _preview_zero)
    monkeypatch.setattr(eda_analysis, "get_study_detail_for_dataset", _phenotype_study)
    ctx = replace(lead_ctx, tool_call_id="call_1")
    returned = await eda_analysis.preview_eda_subset(ctx, entity_id=_ENTITY)
    summaries = [
        chunk.data
        for chunk in returned.metadata
        if isinstance(chunk, DataChunk) and chunk.type == "data-tool-summary"
    ]
    assert summaries == [
        {
            "toolCallId": "call_1",
            "summary": "0 of 4,279 Gene Phenotype Data",
            "status": "empty",
        }
    ]


async def test_a_subset_that_narrows_nothing_says_so(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    """A filter on a child entity can leave the parent entity whole."""
    monkeypatch.setattr(eda_analysis, "bound_analysis", _bound)
    monkeypatch.setattr(eda_analysis, "read_analysis", _read_detail)
    monkeypatch.setattr(eda_analysis, "preview_subset", _preview_whole_entity)
    monkeypatch.setattr(eda_analysis, "get_study_detail_for_dataset", _phenotype_study)
    returned = await eda_analysis.preview_eda_subset(lead_ctx, entity_id=_ENTITY)
    assert "narrow nothing here" in returned.return_value.guidance


async def test_a_multi_valued_distribution_warns_that_the_values_do_not_partition(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    monkeypatch.setattr(eda_analysis, "bound_analysis", _bound)
    monkeypatch.setattr(eda_analysis, "read_analysis", _read_detail)
    monkeypatch.setattr(eda_analysis, "preview_subset", _preview_ok)
    monkeypatch.setattr(eda_analysis, "get_study_detail_for_dataset", _phenotype_study)
    returned = await eda_analysis.preview_eda_subset(
        lead_ctx, entity_id=_ENTITY, distribution_variable_id="VAR_035294d0"
    )
    assert returned.return_value.is_multi_valued is True
    assert "several values per record" in returned.return_value.guidance


async def test_a_preview_reports_the_records_with_no_value_for_the_variable(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    monkeypatch.setattr(eda_analysis, "bound_analysis", _bound)
    monkeypatch.setattr(eda_analysis, "read_analysis", _read_detail)
    monkeypatch.setattr(eda_analysis, "preview_subset", _preview_with_missing)
    monkeypatch.setattr(eda_analysis, "get_study_detail_for_dataset", _phenotype_study)
    returned = await eda_analysis.preview_eda_subset(
        lead_ctx, entity_id=_ENTITY, distribution_variable_id="VAR_035294d0"
    )
    assert returned.return_value.num_missing_cases == 12
    assert "12 records" in returned.return_value.guidance


async def test_a_preview_with_no_open_analysis_raises_a_model_retry(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    monkeypatch.setattr(eda_analysis, "bound_analysis", _unbound)
    with pytest.raises(ModelRetry) as excinfo:
        await eda_analysis.preview_eda_subset(lead_ctx, entity_id=_ENTITY)
    assert "open_eda_analysis" in str(excinfo.value)


@pytest.fixture
async def bound_thread(db_cleaner: None, patch_app_db_engine: None) -> UUID:
    """A real thread row, so the binding service can count its mutations."""
    del db_cleaner, patch_app_db_engine
    user_id = uuid4()
    thread_id = uuid4()
    async with async_session_factory() as session:
        session.add(User(id=user_id))
        await session.flush()
        session.add(Conversation(id=thread_id, user_id=user_id))
        await session.commit()
    return thread_id


def _ctx_for(thread_id: UUID) -> RunContext[LeadDeps]:
    state = PipelineState(
        conversation_id=thread_id,
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


async def _apply_filters_ok(_site: str, **_kwargs: object) -> EdaAnalysisDetail:
    return _detail()


async def _real_bump(*, conversation_id: UUID) -> int:
    """The real atomic bump, past the autouse counting stand-in."""
    return await binding.ConversationAnalysesRepository(
        session_factory=async_session_factory
    ).increment(conversation_id=conversation_id)


async def test_the_analysis_state_revision_grows_with_every_mutation(
    monkeypatch: pytest.MonkeyPatch,
    revisions: _Revisions,
    bound_thread: UUID,
) -> None:
    """Two surfaces edit one analysis, so each part must say which write it is."""
    del revisions
    monkeypatch.setattr(binding, "bump_analysis_revision", _real_bump)
    monkeypatch.setattr(binding, "open_analysis", lambda *_a, **_k: _resolved("A"))
    monkeypatch.setattr(binding, "read_analysis", _read_detail)
    monkeypatch.setattr(eda_analysis, "get_study_detail_for_dataset", _phenotype_study)
    monkeypatch.setattr(binding, "get_study_detail_for_dataset", _phenotype_study)
    monkeypatch.setattr(binding, "patch_subset", _apply_filters_ok)

    ctx = _ctx_for(bound_thread)
    opened = await eda_analysis.open_eda_analysis(
        ctx, dataset_id=_DATASET, purpose="keep the berghei rows"
    )
    filtered = await eda_analysis.set_eda_filters(
        ctx,
        dataset_id=_DATASET,
        filters=[
            EdaStringSetFilter(
                entity_id=_ENTITY,
                variable_id="VAR_035294d0",
                string_set=["P. berghei"],
            )
        ],
    )
    first = opened.metadata[0].data["revision"]
    second = filtered.metadata[0].data["revision"]
    assert first == 1
    assert second == 2


async def test_search_eda_studies_carries_the_name_match_guidance(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    """An unbuilt index degrades to a name match, and the model is told."""
    card = StudyCard(
        dataset_id="DS_heat",
        study_id="STUDY_heat",
        display_name="Heat shock response",
        short_display_name="",
        description="",
        source_type="curated",
    )

    async def by_name(_site: str, _query: str, limit: int = 5) -> StudySearch:
        del limit
        return StudySearch(cards=[card], guidance=NAME_MATCH_GUIDANCE)

    monkeypatch.setattr(eda_catalog, "search_studies", by_name)
    result = (
        await eda_catalog.search_eda_studies(lead_ctx, query="gametocyte")
    ).return_value

    assert [study.dataset_id for study in result.studies] == ["DS_heat"]
    assert result.guidance.startswith(NAME_MATCH_GUIDANCE)

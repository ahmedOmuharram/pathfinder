"""Acceptance: the data-eda payloads, their registry, and the EDA toolset.

Values come from the live-verified EDA knowledge bundle. Fixtures are inline.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from assistant_core.conversation.stream_parts.registry import StreamPartRegistry
from assistant_core.persistence.models import Conversation
from pydantic import ValidationError
from pydantic_ai.toolsets.function import FunctionToolset
from pydantic_ai.toolsets.wrapper import WrapperToolset
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pathfinder.persistence.models import User

parts = pytest.importorskip("shared_py.stream_parts.eda")
registration = pytest.importorskip("pathfinder.ai.eda_stream_parts")
toolset_module = pytest.importorskip("pathfinder.ai.tools.toolsets.eda")
repository = pytest.importorskip(
    "pathfinder.persistence.repositories.conversation_analysis"
)

pytestmark = [pytest.mark.eda_acceptance]

_ANALYSIS_STATE_KEYS = {
    "siteId",
    "datasetId",
    "studyId",
    "analysisId",
    "revision",
    "studyDisplayName",
    "displayName",
    "numFilters",
    "numComputations",
    "filters",
    "filterSummaries",
    "entityCounts",
    "canExportRows",
}

_EDA_TOOLS = {
    "search_eda_studies",
    "describe_eda_study",
    "open_eda_analysis",
    "set_eda_filters",
    "preview_eda_subset",
    "run_eda_compute",
    "create_eda_step",
}

_KINDS = {
    "data-eda.analysis-state",
    "data-eda.subset-preview",
    "data-eda.viz",
}


def _entity_count() -> object:
    return parts.EdaEntityCount(
        entity_id="GENE_PHENOTYPE_DATA_ENTITY",
        entity_display_name="Gene phenotype",
        count=4011,
        unfiltered_count=4279,
    )


def _function_toolset(toolset: object) -> FunctionToolset:
    while isinstance(toolset, WrapperToolset):
        toolset = toolset.wrapped
    assert isinstance(toolset, FunctionToolset)
    return toolset


def test_the_analysis_state_serializes_exactly_the_pinned_camel_case_keys() -> None:
    state = parts.EdaAnalysisState(
        site_id="plasmodb",
        dataset_id="DS_53f554ec6a",
        study_id="STUDY_53f554ec6a",
        analysis_id="t4fszEJ",
        revision=None,
        study_display_name="Rodent malaria phenotypes",
        display_name="berghei subset",
        num_filters=1,
        num_computations=0,
        filters=[
            {
                "entityId": "GENE_PHENOTYPE_DATA_ENTITY",
                "variableId": "VAR_035294d0",
                "type": "stringSet",
                "stringSet": ["P. berghei"],
            }
        ],
        filter_summaries=["Species is one of P. berghei"],
        entity_counts=[_entity_count()],
        can_export_rows=True,
    )
    dumped = state.model_dump(by_alias=True)
    assert set(dumped) == _ANALYSIS_STATE_KEYS
    assert dumped["revision"] is None
    assert dumped["analysisId"] == "t4fszEJ"
    assert dumped["filters"][0]["stringSet"] == ["P. berghei"]
    assert dumped["entityCounts"] == [
        {
            "entityId": "GENE_PHENOTYPE_DATA_ENTITY",
            "entityDisplayName": "Gene phenotype",
            "count": 4011,
            "unfilteredCount": 4279,
        }
    ]


def test_a_subset_preview_carries_the_multi_valued_species_distribution() -> None:
    """4011 + 4130 + 268 = 8409 values over 4279 rows."""
    preview = parts.EdaSubsetPreviewPart(
        dataset_id="DS_53f554ec6a",
        analysis_id="t4fszEJ",
        entity_counts=[_entity_count()],
        distribution=parts.EdaDistributionSeries(
            variable_id="VAR_035294d0",
            variable_display_name="Species",
            labels=["P. berghei", "P. falciparum", "P. yoelii"],
            values=[4011.0, 4130.0, 268.0],
            subset_size=4279,
            num_var_values=8409,
            num_missing_cases=0,
            is_multi_valued=True,
        ),
        distribution_note=None,
    )
    dumped = preview.model_dump(by_alias=True)
    assert dumped["entityCounts"][0]["unfilteredCount"] == 4279
    assert dumped["distribution"]["numVarValues"] == 8409
    assert dumped["distribution"]["isMultiValued"] is True
    assert sum(preview.distribution.values) == 8409.0
    assert preview.distribution.subset_size == 4279


def test_a_distribution_series_refuses_a_label_with_no_value() -> None:
    with pytest.raises(ValidationError):
        parts.EdaDistributionSeries(
            variable_id="VAR_035294d0",
            variable_display_name="Species",
            labels=["P. berghei", "P. falciparum"],
            values=[4011.0],
            subset_size=4279,
            num_var_values=8409,
            num_missing_cases=0,
            is_multi_valued=True,
        )


def test_the_viz_part_carries_the_measured_volcano_totals() -> None:
    viz = parts.EdaVizPart(
        dataset_id="DS_e973eadd57",
        analysis_id="t4fszEJ",
        chart="volcano",
        effect_size_label="log2(Fold Change)",
        effect_size_threshold=1.0,
        significance_threshold=0.05,
        effect_direction="upAndDown",
        total_points=5511,
        retained_points=1543,
        points=[
            parts.EdaVolcanoPoint(
                point_id="PF3D7_0100200",
                effect_size=3.94437533216012,
                p_value=1.95781599815607e-05,
                adjusted_p_value=0.000137772236907279,
                retained=True,
            )
        ],
    )
    dumped = viz.model_dump(by_alias=True)
    assert dumped["chart"] == "volcano"
    assert dumped["totalPoints"] == 5511
    assert dumped["retainedPoints"] == 1543
    assert dumped["points"][0]["pointId"] == "PF3D7_0100200"
    assert dumped["points"][0]["pValue"] == 1.95781599815607e-05


def test_a_volcano_point_with_no_p_value_is_representable() -> None:
    point = parts.EdaVolcanoPoint(
        point_id="PF3D7_MIT04200",
        effect_size=-1.49447459261845,
        p_value=None,
        adjusted_p_value=None,
        retained=False,
    )
    assert point.p_value is None
    assert point.adjusted_p_value is None
    assert point.model_dump(by_alias=True)["pValue"] is None


def _viz_part(**overrides: object) -> object:
    fields: dict[str, object] = {
        "dataset_id": "DS_e973eadd57",
        "analysis_id": "t4fszEJ",
        "chart": "volcano",
        "effect_size_label": "log2(Fold Change)",
        "effect_size_threshold": 1.0,
        "significance_threshold": 0.05,
        "effect_direction": "upAndDown",
        "total_points": 5511,
        "retained_points": 1543,
        "points": [],
    }
    return parts.EdaVizPart.model_validate({**fields, **overrides})


def test_the_chart_union_refuses_a_pie() -> None:
    with pytest.raises(ValidationError):
        _viz_part(chart="pie")


def test_the_part_does_not_police_retained_against_total() -> None:
    """The counts are reported, not cross-checked; only a negative is refused."""
    viz = _viz_part(total_points=1543, retained_points=5511)
    assert viz.retained_points == 5511
    with pytest.raises(ValidationError):
        _viz_part(total_points=-1)


def test_exactly_three_eda_kinds_register() -> None:
    registry = StreamPartRegistry()
    registration.register_eda_stream_parts(registry)
    assert registry.kinds() == _KINDS


def test_the_toolset_carries_exactly_the_seven_pinned_tool_names() -> None:
    tools = _function_toolset(toolset_module.build_toolset()).tools
    assert {tool.name for tool in tools.values()} == _EDA_TOOLS


def test_the_durable_compute_tool_runs_sequential() -> None:
    """A durable tool suspends the graph; a parallel sibling's return is orphaned."""
    tools = _function_toolset(toolset_module.build_toolset()).tools
    by_name = {tool.name: tool for tool in tools.values()}
    assert by_name["run_eda_compute"].sequential is True


@pytest.mark.asyncio
async def test_a_thread_binds_one_analysis_and_starts_at_revision_zero(
    session_maker: async_sessionmaker[AsyncSession],
    db_cleaner: None,
) -> None:
    del db_cleaner
    async with session_maker() as session:
        user = User(id=uuid4())
        session.add(user)
        await session.flush()
        thread = Conversation(id=uuid4(), user_id=user.id)
        session.add(thread)
        await session.commit()

    repo = repository.ConversationAnalysesRepository(session_factory=session_maker)
    assert await repo.get(conversation_id=thread.id) is None

    await repo.bind(
        conversation_id=thread.id,
        site_id="plasmodb",
        dataset_id="DS_53f554ec6a",
        analysis_id="t4fszEJ",
    )
    view = await repo.get(conversation_id=thread.id)
    assert view is not None
    assert view.site_id == "plasmodb"
    assert view.dataset_id == "DS_53f554ec6a"
    assert view.analysis_id == "t4fszEJ"
    assert view.revision == 0

    await repo.bind(
        conversation_id=thread.id,
        site_id="plasmodb",
        dataset_id="DS_eeca6a5476",
        analysis_id="Kj2mQ7a",
    )
    replaced = await repo.get(conversation_id=thread.id)
    assert replaced is not None
    assert replaced.dataset_id == "DS_eeca6a5476"
    assert replaced.analysis_id == "Kj2mQ7a"

    await repo.unbind(conversation_id=thread.id)
    assert await repo.get(conversation_id=thread.id) is None

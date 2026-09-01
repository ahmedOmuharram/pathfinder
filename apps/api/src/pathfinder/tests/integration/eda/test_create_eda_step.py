"""create_eda_step builds an ordinary WDK step through the existing service."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

import pytest
from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.lead.sub_agent_tools import LeadDeps
from pathfinder.ai.tools.standalone import eda_step
from pathfinder.domain.strategy.session import StrategyGraph, StrategySession
from pathfinder.integrations.eda.models import (
    EdaAnalysisDescriptor,
    EdaAnalysisDetail,
    EdaComparator,
    EdaComputation,
    EdaComputationDescriptor,
    EdaDifferentialExpressionConfig,
    EdaLabeledRange,
    EdaStringSetFilter,
    EdaSubsetDescriptor,
    EdaVariableSpec,
)
from pathfinder.persistence.models import ConversationAnalysisView
from pathfinder.platform.errors import ValidationError
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService
from pathfinder.services.strategies.commit import CommitResult
from pathfinder.services.strategies.sync import SyncResult

pytestmark = pytest.mark.asyncio

_DATASET = "DS_53f554ec6a"
_ENTITY = "GENE_PHENOTYPE_DATA_ENTITY"
_ANALYSIS = "t4fszEJ"


def _never_factory() -> AsyncSession:
    msg = "db factory should not be called in these tests"
    raise AssertionError(msg)


@pytest.fixture
def lead_ctx() -> RunContext[LeadDeps]:
    session = StrategySession(site_id="plasmodb")
    session.add_graph(StrategyGraph("g1", "Test", "plasmodb"))
    state = PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
        user_prompt="export the febrile subset",
    )
    runtime = Context(
        site_id="plasmodb",
        user_id=state.user_id,
        strategy_session=session,
        db_session_factory=_never_factory,
        web_search_service=WebSearchService(),
        literature_search_service=LiteratureSearchService(),
        cancel_event=asyncio.Event(),
    )
    deps = LeadDeps(state=state, intent=None, runtime=runtime, retrieved_memories=[])
    return RunContext(deps=deps, model=TestModel(), usage=RunUsage(), messages=[])


async def _bound(_ctx: object) -> ConversationAnalysisView:
    return ConversationAnalysisView(
        site_id="plasmodb",
        dataset_id=_DATASET,
        analysis_id=_ANALYSIS,
        revision=1,
    )


async def _unbound(_ctx: object) -> ConversationAnalysisView | None:
    return None


def _computation() -> EdaComputation:
    return EdaComputation(
        computation_id="c1",
        descriptor=EdaComputationDescriptor(
            configuration=EdaDifferentialExpressionConfig(
                identifier_variable=EdaVariableSpec(
                    entity_id=_ENTITY, variable_id="VAR_gene"
                ),
                value_variable=EdaVariableSpec(
                    entity_id=_ENTITY, variable_id="VAR_counts"
                ),
                comparator=EdaComparator(
                    variable=EdaVariableSpec(
                        entity_id=_ENTITY, variable_id="VAR_state"
                    ),
                    group_a=[EdaLabeledRange(label="febrile")],
                    group_b=[EdaLabeledRange(label="normal")],
                ),
            )
        ),
    )


def _detail(*, with_computation: bool) -> EdaAnalysisDetail:
    return EdaAnalysisDetail(
        analysis_id=_ANALYSIS,
        display_name="berghei subset",
        study_id=_DATASET,
        descriptor=EdaAnalysisDescriptor(
            subset=EdaSubsetDescriptor(
                descriptor=[
                    EdaStringSetFilter(
                        entity_id=_ENTITY,
                        variable_id="VAR_035294d0",
                        string_set=["P. berghei"],
                    )
                ]
            ),
            computations=[_computation()] if with_computation else [],
        ),
    )


async def _read_detail(_site: str, *, analysis_id: str) -> EdaAnalysisDetail:
    assert analysis_id == _ANALYSIS
    return _detail(with_computation=False)


async def _read_detail_with_computation(
    _site: str, *, analysis_id: str
) -> EdaAnalysisDetail:
    assert analysis_id == _ANALYSIS
    return _detail(with_computation=True)


def _commit_result(*, wdk_url: str | None = None) -> CommitResult:
    return CommitResult(
        description="added a step",
        sync_result=SyncResult(
            wdk_strategy_id=330423363,
            wdk_url=wdk_url,
            root_step_id=1,
            counts={},
            root_count=132,
            zero_step_ids=[],
            step_count=1,
        ),
    )


def _recording_commit(
    applied: list[Any], *, wdk_url: str | None = None
) -> Callable[..., Awaitable[CommitResult]]:
    async def commit(*, deps: object, ops: list[Any]) -> CommitResult:
        assert deps is not None
        applied.append(ops)
        return _commit_result(wdk_url=wdk_url)

    return commit


async def test_a_subset_export_uses_the_generic_subset_search(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    applied: list[Any] = []
    monkeypatch.setattr(eda_step, "bound_analysis", _bound)
    monkeypatch.setattr(eda_step, "read_analysis", _read_detail)
    monkeypatch.setattr(
        eda_step, "apply_operations_and_commit", _recording_commit(applied)
    )

    returned = await eda_step.create_eda_step(lead_ctx)

    step = applied[0][0].step
    assert step.search_name == "GenesByEdaSubset"
    assert step.parameters["eda_dataset_id"].value == _DATASET
    spec = json.loads(step.parameters["eda_analysis_spec"].value)
    assert spec["studyId"] == _DATASET
    assert spec["descriptor"]["subset"]["descriptor"][0]["stringSet"] == ["P. berghei"]
    assert step.display_name == "berghei subset"
    assert returned.return_value.search_name == "GenesByEdaSubset"
    assert returned.return_value.is_compute_backed is False
    assert returned.return_value.step_id == step.id
    assert "330423363" in returned.return_value.guidance


async def test_a_compute_export_uses_the_viz_with_compute_search(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    applied: list[Any] = []
    monkeypatch.setattr(eda_step, "bound_analysis", _bound)
    monkeypatch.setattr(eda_step, "read_analysis", _read_detail_with_computation)
    monkeypatch.setattr(
        eda_step, "apply_operations_and_commit", _recording_commit(applied)
    )

    returned = await eda_step.create_eda_step(
        lead_ctx,
        effect_size_threshold=1.0,
        significance_threshold=0.05,
    )

    step = applied[0][0].step
    assert step.search_name == "GenesByEdaVizWithCompute"
    spec = json.loads(step.parameters["eda_analysis_spec"].value)
    viz = spec["descriptor"]["computations"][0]["visualizations"][0]["descriptor"]
    assert viz["configuration"]["effectSizeThreshold"] == 1.0
    assert viz["configuration"]["significanceThreshold"] == 0.05
    assert viz["configuration"]["effectDirection"] == "upAndDown"
    assert returned.return_value.search_name == "GenesByEdaVizWithCompute"
    assert returned.return_value.is_compute_backed is True


async def test_an_explicit_search_name_wins_over_the_generic_one(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    """A per-dataset search already run by the researcher is still exportable."""
    applied: list[Any] = []
    monkeypatch.setattr(eda_step, "bound_analysis", _bound)
    monkeypatch.setattr(eda_step, "read_analysis", _read_detail)
    monkeypatch.setattr(
        eda_step, "apply_operations_and_commit", _recording_commit(applied)
    )

    await eda_step.create_eda_step(lead_ctx, search_name="GenesByRNASeqDESeq")

    assert applied[0][0].step.search_name == "GenesByRNASeqDESeq"


async def test_the_thresholds_are_written_into_the_analysis_not_into_a_parameter(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    """The thresholds a user drags ARE the search parameters; they ride in the JSON."""
    applied: list[Any] = []
    monkeypatch.setattr(eda_step, "bound_analysis", _bound)
    monkeypatch.setattr(eda_step, "read_analysis", _read_detail_with_computation)
    monkeypatch.setattr(
        eda_step, "apply_operations_and_commit", _recording_commit(applied)
    )

    await eda_step.create_eda_step(
        lead_ctx, effect_size_threshold=2.0, significance_threshold=0.01
    )

    step = applied[0][0].step
    assert set(step.parameters) == {"eda_dataset_id", "eda_analysis_spec"}


async def test_a_compute_export_without_thresholds_raises_a_model_retry(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    """The plugin throws unless the volcano carries both thresholds."""
    monkeypatch.setattr(eda_step, "bound_analysis", _bound)
    monkeypatch.setattr(eda_step, "read_analysis", _read_detail_with_computation)

    with pytest.raises(ModelRetry) as excinfo:
        await eda_step.create_eda_step(lead_ctx, effect_size_threshold=1.0)

    message = str(excinfo.value)
    assert "significance_threshold" in message


async def test_a_significance_threshold_alone_raises_a_model_retry(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    """The mirror of the pair guard: neither threshold may travel alone."""
    monkeypatch.setattr(eda_step, "bound_analysis", _bound)
    monkeypatch.setattr(eda_step, "read_analysis", _read_detail_with_computation)

    with pytest.raises(ModelRetry) as excinfo:
        await eda_step.create_eda_step(lead_ctx, significance_threshold=0.05)

    assert "effect_size_threshold" in str(excinfo.value)


async def test_a_compute_export_with_no_computation_names_the_compute_tool(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    monkeypatch.setattr(eda_step, "bound_analysis", _bound)
    monkeypatch.setattr(eda_step, "read_analysis", _read_detail)

    with pytest.raises(ModelRetry) as excinfo:
        await eda_step.create_eda_step(
            lead_ctx, effect_size_threshold=1.0, significance_threshold=0.05
        )

    assert "run_eda_compute" in str(excinfo.value)


async def test_a_step_with_no_open_analysis_raises_a_model_retry(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    monkeypatch.setattr(eda_step, "bound_analysis", _unbound)

    with pytest.raises(ModelRetry) as excinfo:
        await eda_step.create_eda_step(lead_ctx)

    assert "open_eda_analysis" in str(excinfo.value)


async def test_the_step_emits_the_parts_the_workbench_already_listens_to(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    monkeypatch.setattr(eda_step, "bound_analysis", _bound)
    monkeypatch.setattr(eda_step, "read_analysis", _read_detail)
    monkeypatch.setattr(eda_step, "apply_operations_and_commit", _recording_commit([]))

    returned = await eda_step.create_eda_step(lead_ctx)

    kinds = [c.type for c in returned.metadata]
    assert "data-graph-snapshot" in kinds
    assert "data-strategy-link" not in kinds


async def test_a_commit_with_a_wdk_url_also_emits_the_strategy_link(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    monkeypatch.setattr(eda_step, "bound_analysis", _bound)
    monkeypatch.setattr(eda_step, "read_analysis", _read_detail)
    monkeypatch.setattr(
        eda_step,
        "apply_operations_and_commit",
        _recording_commit([], wdk_url="https://plasmodb.org/plasmo/app/workspace"),
    )

    returned = await eda_step.create_eda_step(lead_ctx)

    kinds = [c.type for c in returned.metadata]
    assert kinds == ["data-graph-snapshot", "data-strategy-link"]
    assert returned.return_value.wdk_strategy_id == 330423363


async def test_attaching_into_a_slot_builds_the_slot_attach_point(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    applied: list[Any] = []
    monkeypatch.setattr(eda_step, "bound_analysis", _bound)
    monkeypatch.setattr(eda_step, "read_analysis", _read_detail)
    monkeypatch.setattr(
        eda_step, "apply_operations_and_commit", _recording_commit(applied)
    )

    await eda_step.create_eda_step(lead_ctx, attach_to_step_id="s1", slot="secondary")

    attach = applied[0][0].attach
    assert attach.mode == "into-slot"
    assert attach.target_step_id == "s1"
    assert attach.slot == "secondary"


async def test_a_step_with_no_attach_point_becomes_a_new_root(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    applied: list[Any] = []
    monkeypatch.setattr(eda_step, "bound_analysis", _bound)
    monkeypatch.setattr(eda_step, "read_analysis", _read_detail)
    monkeypatch.setattr(
        eda_step, "apply_operations_and_commit", _recording_commit(applied)
    )

    await eda_step.create_eda_step(lead_ctx)

    assert applied[0][0].attach.mode == "new-root"


async def test_a_slot_without_a_target_step_raises_a_model_retry(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    monkeypatch.setattr(eda_step, "bound_analysis", _bound)
    monkeypatch.setattr(eda_step, "read_analysis", _read_detail)

    with pytest.raises(ModelRetry) as excinfo:
        await eda_step.create_eda_step(lead_ctx, slot="secondary")

    assert "attachToStepId" in str(excinfo.value)


async def test_a_target_step_without_a_slot_raises_a_model_retry(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    monkeypatch.setattr(eda_step, "bound_analysis", _bound)
    monkeypatch.setattr(eda_step, "read_analysis", _read_detail)

    with pytest.raises(ModelRetry) as excinfo:
        await eda_step.create_eda_step(lead_ctx, attach_to_step_id="s1")

    assert "slot" in str(excinfo.value)


async def test_a_step_wdk_rejected_is_reported_rather_than_hidden(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    """The commit reports a rejection on the step; the model must see it."""

    async def commit(*, deps: object, ops: list[Any]) -> CommitResult:
        del deps, ops
        return CommitResult(description="added", failed_step_ids=["step_1"])

    monkeypatch.setattr(eda_step, "bound_analysis", _bound)
    monkeypatch.setattr(eda_step, "read_analysis", _read_detail)
    monkeypatch.setattr(eda_step, "apply_operations_and_commit", commit)

    returned = await eda_step.create_eda_step(lead_ctx)

    assert returned.return_value.failed_step_ids == ["step_1"]
    assert returned.return_value.wdk_strategy_id is None


async def test_a_session_with_no_graph_fails_loudly(
    monkeypatch: pytest.MonkeyPatch, lead_ctx: RunContext[LeadDeps]
) -> None:
    """A turn always hydrates a graph, so its absence is a wiring fault."""
    monkeypatch.setattr(eda_step, "bound_analysis", _bound)
    monkeypatch.setattr(eda_step, "read_analysis", _read_detail)
    lead_ctx.deps.runtime.strategy_session.graph = None

    with pytest.raises(ValidationError) as excinfo:
        await eda_step.create_eda_step(lead_ctx)

    assert "No active strategy graph" in str(excinfo.value)

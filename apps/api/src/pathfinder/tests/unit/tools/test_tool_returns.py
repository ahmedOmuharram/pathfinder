"""Tests for tool conversions to `ToolReturn` with typed metadata chunks.

Each test verifies that the tool returns `ToolReturn` with the correct
`return_value` type and emits the expected `DataChunk`/`SourceUrlChunk`
items in `metadata` for the new AI SDK v6 streaming protocol.

Only chunks of type `DataChunk`, `SourceUrlChunk`, `SourceDocumentChunk`,
`FileChunk` survive adapter filtering. Nothing else belongs in metadata.
"""

from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai.messages import ToolReturn
from pydantic_ai.ui.vercel_ai.response_types import (
    DataChunk,
    SourceUrlChunk,
)

from pathfinder.ai.agents.state import AgentToolState, SearchOverview
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.graph.state import ProblemFrame
from pathfinder.ai.tools.standalone._workbench_models import (
    GeneSetCreatedResponse,
)
from pathfinder.ai.tools.standalone.conversation import (
    clear_strategy,
    rename_strategy,
)
from pathfinder.ai.tools.standalone.problem_framing import set_problem_frame
from pathfinder.ai.tools.standalone.research import (
    literature_search,
    web_search,
)
from pathfinder.ai.tools.standalone.strategy_build import (
    combine_steps,
    create_leaf_step,
    transform_step,
)
from pathfinder.ai.tools.standalone.strategy_edit import (
    delete_step,
    update_step,
)
from pathfinder.ai.tools.standalone.workbench import create_workbench_gene_set
from pathfinder.domain.research.citations import Citation
from pathfinder.domain.strategy.ast import PlanStepNode
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.services.research.processing import (
    EnrichedPaper,
    LiteratureSearchResponse,
)
from pathfinder.services.research.web_search import (
    SearchDiagnostics,
    WebSearchResponse,
    WebSearchResult,
)
from pathfinder.services.strategies.step_creation import StepCreationResult

# ── Helpers ────────────────────────────────────────────────────────────────


def _make_session(site_id: str = "plasmodb") -> StrategySession:
    session = StrategySession(site_id=site_id)
    graph = session.create_graph("Strategy Under Test")
    graph.record_type = "transcript"
    return session


def _make_deps(
    session: StrategySession,
    *,
    agent_state: AgentToolState | None = None,
    web_search_service: object | None = None,
    literature_search_service: object | None = None,
) -> AgentDeps:
    return AgentDeps(
        site_id=session.site_id,
        strategy_session=session,
        agent_state=agent_state or AgentToolState(),
        web_search_service=cast("object", web_search_service),  # type: ignore[arg-type]
        literature_search_service=cast("object", literature_search_service),  # type: ignore[arg-type]
    )


def _make_ctx(deps: AgentDeps) -> MagicMock:
    ctx = MagicMock()
    ctx.deps = deps
    return ctx


def _register_search(state: AgentToolState, search_name: str) -> None:
    state.register_search(
        search_name,
        SearchOverview(
            search_name=search_name,
            display_name=f"{search_name} Display",
            record_type="transcript",
            description=f"Test search {search_name}",
            parameter_names=["organism"],
            required_params=["organism"],
        ),
    )


def _metadata_chunks(result: ToolReturn[object]) -> list[object]:
    return list(result.metadata or [])


def _data_chunks(result: ToolReturn[object], type_name: str) -> list[DataChunk]:
    return [
        c
        for c in _metadata_chunks(result)
        if isinstance(c, DataChunk) and c.type == type_name
    ]


def _source_url_chunks(result: ToolReturn[object]) -> list[SourceUrlChunk]:
    return [c for c in _metadata_chunks(result) if isinstance(c, SourceUrlChunk)]


# ── set_problem_frame ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_set_problem_frame_returns_tool_return_with_problem_frame_data():
    """set_problem_frame should emit data-problem-frame DataChunk."""
    session = _make_session()
    deps = _make_deps(session)
    ctx = _make_ctx(deps)

    frame = ProblemFrame(
        user_goal="find drug targets for PfATP4",
        interpreted_goal="identify essential plasmodium genes related to ATP4",
        organism_scope="plasmodb",
        record_type="transcript",
        biological_entities=["PfATP4"],
        ready_for_wdk_discovery=True,
        confidence=0.9,
    )
    result = await set_problem_frame(ctx, frame)

    assert isinstance(result, ToolReturn)
    # return_value preserves the existing ProblemFrameResponse shape
    assert result.return_value.problem_frame.user_goal == "find drug targets for PfATP4"
    # Exactly one data-problem-frame DataChunk with the full frame
    chunks = _data_chunks(result, "data-problem-frame")
    assert len(chunks) == 1
    payload = chunks[0].data
    assert payload["siteId"] == "plasmodb"
    assert payload["userGoal"] == "find drug targets for PfATP4"
    assert payload["interpretedGoal"] == (
        "identify essential plasmodium genes related to ATP4"
    )
    assert payload["organismScope"] == "plasmodb"
    assert payload["recordType"] == "transcript"
    assert "PfATP4" in payload["biologicalEntities"]
    assert payload["readyForWdkDiscovery"] is True
    assert payload["confidence"] == 0.9


# ── literature_search ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_literature_search_emits_source_url_chunk_per_citation():
    """literature_search should emit one SourceUrlChunk per citation."""
    session = _make_session()
    fake_service = AsyncMock()
    fake_response = LiteratureSearchResponse(
        query="malaria drug targets",
        source="all",
        sort="relevance",
        include_abstract=False,
        abstract_max_chars=2000,
        max_authors=2,
        filters=__import__(
            "pathfinder.domain.research.citations",
            fromlist=["LiteratureFilters"],
        ).LiteratureFilters(),
        results=[
            EnrichedPaper(
                title="Ortholog analysis of PfATP4",
                year=2022,
                doi="10.1/x",
                url="https://example.com/paper1",
                authors=["Smith J"],
                source="pubmed",
            ),
        ],
        citations=[
            Citation(
                id="c1",
                source="pubmed",
                title="Ortholog analysis of PfATP4",
                url="https://example.com/paper1",
                year=2022,
                tag="smith2022",
            ),
            Citation(
                id="c2",
                source="openalex",
                title="Secondary citation",
                url="https://example.com/paper2",
                year=2023,
                tag="jones2023",
            ),
        ],
    )
    fake_service.search = AsyncMock(return_value=fake_response)
    deps = _make_deps(session, literature_search_service=fake_service)
    ctx = _make_ctx(deps)

    result = await literature_search(ctx, "malaria drug targets")

    assert isinstance(result, ToolReturn)
    assert len(result.return_value.citations) == 2
    url_chunks = _source_url_chunks(result)
    assert len(url_chunks) == 2
    urls = {c.url for c in url_chunks}
    assert urls == {"https://example.com/paper1", "https://example.com/paper2"}


@pytest.mark.asyncio
async def test_web_search_emits_source_url_chunk_per_citation():
    """web_search should emit one SourceUrlChunk per citation."""
    session = _make_session()
    fake_service = AsyncMock()
    fake_response = WebSearchResponse(
        query="malaria",
        effective_query="malaria",
        search_adjusted=False,
        search_diagnostics=SearchDiagnostics(
            provider="test", latency_ms=0, total_results=1, returned=1
        ),
        results=[
            WebSearchResult(
                title="Malaria overview",
                url="https://example.com/malaria",
                snippet="...",
            ),
        ],
        citations=[
            Citation(
                id="c1",
                source="web",
                title="Malaria overview",
                url="https://example.com/malaria",
                tag="malaria1",
            ),
        ],
    )
    fake_service.search = AsyncMock(return_value=fake_response)
    deps = _make_deps(session, web_search_service=fake_service)
    ctx = _make_ctx(deps)

    result = await web_search(ctx, "malaria")

    assert isinstance(result, ToolReturn)
    url_chunks = _source_url_chunks(result)
    assert len(url_chunks) == 1
    assert url_chunks[0].url == "https://example.com/malaria"


# ── create_leaf_step (graph mutation) ──────────────────────────────────────


@pytest.mark.asyncio
@patch(
    "pathfinder.ai.tools.standalone.strategy_build.create_step",
    new_callable=AsyncMock,
)
async def test_create_leaf_step_emits_graph_snapshot_and_strategy_update(
    mock_create: AsyncMock,
):
    """create_leaf_step should emit data-graph-snapshot + data-strategy-update."""
    session = _make_session()
    agent_state = AgentToolState()
    _register_search(agent_state, "GenesByTaxon")
    deps = _make_deps(session, agent_state=agent_state)
    ctx = _make_ctx(deps)

    graph = session.get_graph(None)
    assert graph is not None

    new_step = PlanStepNode(
        search_name="GenesByTaxon",
        display_name="Test Step",
        parameters={"organism": "plasmodium"},
    )
    graph.steps[new_step.id] = new_step
    graph.roots.add(new_step.id)
    graph.last_step_id = new_step.id
    mock_create.return_value = StepCreationResult(
        step=new_step, step_id=new_step.id, error=None
    )

    result = await create_leaf_step(
        ctx,
        search_name="GenesByTaxon",
        parameters={"organism": "plasmodium"},
    )

    assert isinstance(result, ToolReturn)
    # return_value is the existing StepOkResponse model
    assert result.return_value.step.id == new_step.id

    # data-graph-snapshot DataChunk present
    graph_chunks = _data_chunks(result, "data-graph-snapshot")
    assert len(graph_chunks) == 1
    snap = graph_chunks[0].data
    assert snap["strategyId"] == graph.id
    assert snap["geneCount"] == 0  # No sync_state count yet
    assert len(snap["nodes"]) == 1

    # data-strategy-update DataChunk present
    update_chunks = _data_chunks(result, "data-strategy-update")
    assert len(update_chunks) == 1
    patch_data = update_chunks[0].data
    assert patch_data["strategyId"] == graph.id
    assert patch_data["operation"] == "add_step"
    assert patch_data["step"] is not None


# ── combine_steps ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
@patch(
    "pathfinder.ai.tools.standalone.strategy_build.create_step",
    new_callable=AsyncMock,
)
async def test_combine_steps_emits_graph_snapshot_and_strategy_update(
    mock_create: AsyncMock,
):
    """combine_steps should emit data-graph-snapshot + data-strategy-update."""
    session = _make_session()
    deps = _make_deps(session)
    ctx = _make_ctx(deps)

    graph = session.get_graph(None)
    assert graph is not None

    step_a = PlanStepNode(
        search_name="GenesByTaxon",
        display_name="A",
        parameters={"organism": "plasmodb"},
    )
    step_b = PlanStepNode(
        search_name="GenesByTaxon",
        display_name="B",
        parameters={"organism": "toxodb"},
    )
    graph.steps[step_a.id] = step_a
    graph.steps[step_b.id] = step_b

    combined = PlanStepNode(
        search_name="__combine__",
        operator=__import__(
            "pathfinder.domain.strategy.ops", fromlist=["CombineOp"]
        ).CombineOp.INTERSECT,
        primary_input=step_a,
        secondary_input=step_b,
    )
    graph.steps[combined.id] = combined
    graph.roots.add(combined.id)
    graph.last_step_id = combined.id
    mock_create.return_value = StepCreationResult(
        step=combined, step_id=combined.id, error=None
    )

    result = await combine_steps(
        ctx,
        step_a_id=step_a.id,
        step_b_id=step_b.id,
        operator="INTERSECT",
    )

    assert isinstance(result, ToolReturn)
    assert _data_chunks(result, "data-graph-snapshot")
    assert _data_chunks(result, "data-strategy-update")


# ── transform_step ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
@patch(
    "pathfinder.ai.tools.standalone.strategy_build.create_step",
    new_callable=AsyncMock,
)
async def test_transform_step_emits_graph_snapshot_and_strategy_update(
    mock_create: AsyncMock,
):
    """transform_step should emit data-graph-snapshot + data-strategy-update."""
    session = _make_session()
    deps = _make_deps(session)
    ctx = _make_ctx(deps)

    graph = session.get_graph(None)
    assert graph is not None

    base_step = PlanStepNode(
        search_name="GenesByTaxon",
        display_name="Base",
        parameters={"organism": "plasmodb"},
    )
    graph.steps[base_step.id] = base_step

    transform = PlanStepNode(
        search_name="GenesByOrthologs",
        display_name="Transformed",
        primary_input=base_step,
    )
    graph.steps[transform.id] = transform
    graph.roots.add(transform.id)
    graph.last_step_id = transform.id
    mock_create.return_value = StepCreationResult(
        step=transform, step_id=transform.id, error=None
    )

    result = await transform_step(
        ctx,
        input_step_id=base_step.id,
        transform_name="GenesByOrthologs",
    )

    assert isinstance(result, ToolReturn)
    assert _data_chunks(result, "data-graph-snapshot")
    assert _data_chunks(result, "data-strategy-update")


# ── update_step ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_step_emits_graph_snapshot_and_strategy_update():
    session = _make_session()
    deps = _make_deps(session)
    ctx = _make_ctx(deps)

    graph = session.get_graph(None)
    assert graph is not None

    step = PlanStepNode(
        search_name="GenesByTaxon",
        display_name="Existing",
        parameters={"organism": "plasmodb"},
    )
    graph.steps[step.id] = step
    graph.roots.add(step.id)

    result = await update_step(ctx, step_id=step.id, display_name="Updated")

    assert isinstance(result, ToolReturn)
    assert _data_chunks(result, "data-graph-snapshot")
    assert _data_chunks(result, "data-strategy-update")


# ── delete_step ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_step_emits_graph_snapshot_and_strategy_update():
    session = _make_session()
    deps = _make_deps(session)
    ctx = _make_ctx(deps)

    graph = session.get_graph(None)
    assert graph is not None

    step_a = PlanStepNode(
        search_name="GenesByTaxon",
        display_name="A",
        parameters={"organism": "plasmodb"},
    )
    step_b = PlanStepNode(
        search_name="GenesByTaxon",
        display_name="B",
        parameters={"organism": "toxodb"},
    )
    graph.steps[step_a.id] = step_a
    graph.steps[step_b.id] = step_b
    graph.roots.add(step_a.id)

    result = await delete_step(ctx, step_id=step_b.id)

    assert isinstance(result, ToolReturn)
    assert _data_chunks(result, "data-graph-snapshot")
    assert _data_chunks(result, "data-strategy-update")


# ── rename_strategy ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rename_strategy_emits_strategy_meta_data_chunk():
    """rename_strategy should emit data-strategy-meta DataChunk."""
    session = _make_session()
    deps = _make_deps(session)
    ctx = _make_ctx(deps)

    graph = session.get_graph(None)
    assert graph is not None
    step = PlanStepNode(
        search_name="GenesByTaxon",
        display_name="A",
        parameters={"organism": "plasmodb"},
    )
    graph.steps[step.id] = step
    graph.roots.add(step.id)

    result = await rename_strategy(
        ctx,
        new_name="New Strategy Name",
        description="A better description",
    )

    assert isinstance(result, ToolReturn)
    assert result.return_value.new_name == "New Strategy Name"
    meta_chunks = _data_chunks(result, "data-strategy-meta")
    assert len(meta_chunks) == 1
    data = meta_chunks[0].data
    assert data["strategyId"] == graph.id
    assert data["name"] == "New Strategy Name"


# ── clear_strategy ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_clear_strategy_emits_graph_cleared_data_chunk():
    """clear_strategy should emit data-graph-cleared DataChunk."""
    session = _make_session()
    deps = _make_deps(session)
    ctx = _make_ctx(deps)

    graph = session.get_graph(None)
    assert graph is not None
    # Add a step so "there's something to clear"
    step = PlanStepNode(
        search_name="GenesByTaxon",
        display_name="A",
        parameters={"organism": "plasmodb"},
    )
    graph.steps[step.id] = step
    graph.roots.add(step.id)

    result = await clear_strategy(ctx, confirm=True)

    assert isinstance(result, ToolReturn)
    assert _data_chunks(result, "data-graph-cleared")


# ── create_workbench_gene_set ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_workbench_gene_set_emits_gene_set_data_chunk():
    """create_workbench_gene_set should emit data-gene-set DataChunk."""
    session = _make_session()
    deps = _make_deps(session)
    ctx = _make_ctx(deps)

    result = await create_workbench_gene_set(
        ctx,
        name="Test Gene Set",
        gene_ids=["PF3D7_1222600", "PF3D7_1031000"],
    )

    assert isinstance(result, ToolReturn)
    assert isinstance(result.return_value, GeneSetCreatedResponse)
    chunks = _data_chunks(result, "data-gene-set")
    assert len(chunks) == 1
    data = chunks[0].data
    assert data["name"] == "Test Gene Set"
    assert data["geneCount"] == 2
    assert data["siteId"] == "plasmodb"


# ── ToolErrorPayload short-circuit ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_leaf_step_error_returns_raw_error_without_metadata():
    """When the tool errors out, it returns a ToolErrorPayload (no metadata chunks)."""
    session = _make_session()
    agent_state = AgentToolState()
    # Do NOT register any search — will fail DISCOVERY_REQUIRED gate
    deps = _make_deps(session, agent_state=agent_state)
    ctx = _make_ctx(deps)

    result = await create_leaf_step(
        ctx,
        search_name="UnknownSearch",
        parameters={"organism": "plasmodium"},
    )

    # Errors return plain ToolErrorPayload (no ToolReturn wrapping)
    assert not isinstance(result, ToolReturn)
    assert result.code == "DISCOVERY_REQUIRED"

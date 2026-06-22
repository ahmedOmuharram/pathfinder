"""End-to-end (dispatch level): discover_searches auto-reconciles the active
plan when discovery records a ``replaces`` link — the Lead does no plan editing.
Only the LLM boundary (_stream_sub_agent) is mocked; it stands in for the
discovery sub-agent committing a targeted replacement.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

import pytest
from pydantic_ai import RunContext
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.usage import RunUsage
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.agents.state import ParamVocabSnapshot, SearchOverview
from pathfinder.ai.graph.runtime import AgentDeps, Context
from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.lead import sub_agent_dispatch
from pathfinder.ai.lead.deltas import DiscoveryDelta
from pathfinder.ai.lead.sub_agent_dispatch import discover_searches
from pathfinder.ai.lead.sub_agent_tools import LeadDeps
from pathfinder.domain.parameters.values import MultiPickValue
from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.domain.strategy.plan import (
    ParamStatus,
    PlannedConnection,
    PlannedParameter,
    PlannedStep,
    StepStatus,
    StepType,
    StrategyPlan,
)
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService

pytestmark = pytest.mark.asyncio


def _never_factory() -> AsyncSession:
    msg = "db factory should not be called here"
    raise AssertionError(msg)


def _stub_model() -> FunctionModel:
    def _fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        return ModelResponse(parts=[TextPart(content="ok")])

    async def _stream(messages: list[ModelMessage], info: AgentInfo) -> Any:
        del messages, info
        yield "ok"

    return FunctionModel(_fn, stream_function=_stream, model_name="test")


def _interpro_plan() -> StrategyPlan:
    leaf = PlannedStep(
        id="s1",
        search_name="GenesByInterproDomain",
        display_name="InterPro kinase",
        step_type=StepType.LEAF,
        status=StepStatus.READY,
        parameters=[
            PlannedParameter(
                name="organism",
                display_name="organism",
                param_type="multi-pick-vocabulary",
                value=MultiPickValue(values=["Plasmodium"]),
                status=ParamStatus.SET,
                required=True,
            ),
        ],
    )
    signal = PlannedStep(
        id="s2",
        search_name="GenesWithSignalPeptide",
        display_name="Signal peptide",
        step_type=StepType.LEAF,
        status=StepStatus.READY,
    )
    combine = PlannedStep(
        id="c1",
        search_name="__combine__",
        display_name="Combine",
        step_type=StepType.COMBINE,
        status=StepStatus.READY,
        operator="INTERSECT",
        left_id="s1",
        right_id="s2",
    )
    return StrategyPlan(
        title="t",
        description="d",
        rationale="r",
        steps=[leaf, signal, combine],
        connections=[
            PlannedConnection(from_step="s1", to_step="c1", input_type="primary"),
            PlannedConnection(from_step="s2", to_step="c1", input_type="secondary"),
        ],
    )


def _lead_deps() -> LeadDeps:
    state = PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
        active_plan=_interpro_plan(),
        discovered_searches={
            "GenesByInterproDomain": SearchOverview(
                search_name="GenesByInterproDomain",
                display_name="InterPro",
                record_type="transcript",
                description="",
                parameter_names=["organism"],
                required_params=["organism"],
                selection_status="selected",
            ),
        },
    )
    runtime = Context(
        site_id="plasmodb",
        user_id=uuid4(),
        strategy_session=StrategySession(site_id="plasmodb"),
        db_session_factory=_never_factory,
        web_search_service=WebSearchService(),
        literature_search_service=LiteratureSearchService(),
        cancel_event=asyncio.Event(),
        phase_models={},
        phase_reasoning={},
    )
    return LeadDeps(state=state, intent=None, runtime=runtime, retrieved_memories=[])


def _go_overview() -> SearchOverview:
    ov = SearchOverview(
        search_name="GenesByGoTerm",
        display_name="GO term",
        record_type="transcript",
        description="",
        parameter_names=["organism", "go_term_evidence"],
        required_params=["organism", "go_term_evidence"],
        selection_status="selected",
        replaces="GenesByInterproDomain",
        param_hints={
            "organism": ["Plasmodium"],
            "go_term_evidence": ["Curated", "Computed"],
        },
    )
    return ov.model_copy(
        update={
            "param_vocab": {
                "organism": ParamVocabSnapshot(
                    param_type="multi-pick-vocabulary", required=True
                ),
                "go_term_evidence": ParamVocabSnapshot(
                    param_type="multi-pick-vocabulary",
                    required=True,
                    allowed_values=[
                        VocabOption(value="Curated", display="Curated"),
                        VocabOption(value="Computed", display="Computed"),
                    ],
                ),
            },
        },
    )


async def test_discover_searches_auto_reconciles_active_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_stream(**kwargs: Any) -> DiscoveryDelta:
        # Stand in for the discovery sub-agent committing a targeted swap.
        agent_deps: AgentDeps = kwargs["agent_deps"]
        agent_deps.agent_state.register_search("GenesByGoTerm", _go_overview())
        return DiscoveryDelta(findings_summary="swapped to GO")

    monkeypatch.setattr(sub_agent_dispatch, "_stream_sub_agent", _fake_stream)

    deps = _lead_deps()
    ctx: RunContext[LeadDeps] = RunContext(
        deps=deps, model=_stub_model(), usage=RunUsage()
    )
    await discover_searches(
        ctx,
        reason="denied: use GO not InterPro",
        intent_summary="GO kinase activity search",
        keep_prior_selections=True,
    )

    plan = deps.state.active_plan
    assert plan is not None
    by_id = {s.id: s for s in plan.steps}
    # The InterPro leaf was swapped to GenesByGoTerm, params filled from hints.
    assert by_id["s1"].search_name == "GenesByGoTerm"
    ev = next(p for p in by_id["s1"].parameters if p.name == "go_term_evidence")
    assert ev.value == MultiPickValue(values=["Curated", "Computed"])
    # Topology + the signal-peptide leaf untouched.
    assert by_id["s2"].search_name == "GenesWithSignalPeptide"
    assert by_id["c1"].operator == "INTERSECT"


async def test_reconcile_infers_swap_even_without_keep_prior_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """conv-I case: the model REJECTS the old search + selects the new one but
    sets no replaces link, and the Lead omits keep_prior_selections/supersedes.
    Inference still fires on the reliable reject+select signal, so the plan
    swaps deterministically instead of the Lead thrashing on update_plan."""

    async def _fake_stream(**kwargs: Any) -> DiscoveryDelta:
        agent_deps: AgentDeps = kwargs["agent_deps"]
        agent_deps.agent_state.register_search(
            "GenesByGoTerm", _go_overview().model_copy(update={"replaces": None})
        )
        # The old search is rejected (as 4.1-mini did in conv I); the kept
        # signal-peptide leaf stays selected.
        agent_deps.agent_state.register_search(
            "GenesByInterproDomain",
            SearchOverview(
                search_name="GenesByInterproDomain",
                display_name="InterPro",
                record_type="transcript",
                description="",
                parameter_names=["organism"],
                required_params=["organism"],
                selection_status="rejected",
            ),
        )
        agent_deps.agent_state.register_search(
            "GenesWithSignalPeptide",
            SearchOverview(
                search_name="GenesWithSignalPeptide",
                display_name="Signal peptide",
                record_type="transcript",
                description="",
                parameter_names=["organism"],
                required_params=["organism"],
                selection_status="selected",
            ),
        )
        return DiscoveryDelta(findings_summary="rejected InterPro, selected GO")

    monkeypatch.setattr(sub_agent_dispatch, "_stream_sub_agent", _fake_stream)

    deps = _lead_deps()
    ctx: RunContext[LeadDeps] = RunContext(
        deps=deps, model=_stub_model(), usage=RunUsage()
    )
    await discover_searches(
        ctx,
        reason="denied: use GO not InterPro",
        intent_summary="GO kinase activity search",
    )  # no keep_prior_selections, no supersedes

    plan = deps.state.active_plan
    assert plan is not None
    by_id = {s.id: s for s in plan.steps}
    assert by_id["s1"].search_name == "GenesByGoTerm"
    assert by_id["s2"].search_name == "GenesWithSignalPeptide"


async def test_supersedes_swaps_when_model_leaves_old_selected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The conv-H case: the model selects GO but does NOT set a replaces link
    and leaves InterPro 'selected'. The Lead's ``supersedes`` argument still
    drives the deterministic swap."""

    async def _fake_stream(**kwargs: Any) -> DiscoveryDelta:
        agent_deps: AgentDeps = kwargs["agent_deps"]
        # No replaces link; InterPro stays selected (as 4.1-mini did).
        agent_deps.agent_state.register_search(
            "GenesByGoTerm", _go_overview().model_copy(update={"replaces": None})
        )
        return DiscoveryDelta(findings_summary="selected GO, left InterPro")

    monkeypatch.setattr(sub_agent_dispatch, "_stream_sub_agent", _fake_stream)

    deps = _lead_deps()
    ctx: RunContext[LeadDeps] = RunContext(
        deps=deps, model=_stub_model(), usage=RunUsage()
    )
    await discover_searches(
        ctx,
        reason="denied: use GO not InterPro",
        intent_summary="GO kinase activity search",
        keep_prior_selections=True,
        supersedes="GenesByInterproDomain",
    )

    plan = deps.state.active_plan
    assert plan is not None
    by_id = {s.id: s for s in plan.steps}
    assert by_id["s1"].search_name == "GenesByGoTerm"
    assert by_id["s2"].search_name == "GenesWithSignalPeptide"

"""An edit turn declares what happened to every criterion it started with.

"Keep the rest" was honoured only as far as the model remembered to restate it,
and the reply's claim that the rest was preserved was prose. The claim is now a
comparison the dispatch runs before it accepts FRAME's result.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

import pytest
from pydantic_ai.exceptions import ModelRetry
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.graph.runtime import AgentDeps, Context
from pathfinder.ai.graph.state import PipelineState, StrategyDomainState
from pathfinder.ai.lead import sub_agent_dispatch
from pathfinder.ai.lead.deltas import FrameResult
from pathfinder.ai.lead.sub_agent_dispatch import frame_work_order, run_frame
from pathfinder.ai.lead.sub_agent_tools import LeadDeps
from pathfinder.domain.parameters.values import MultiPickValue, NumberValue
from pathfinder.domain.strategy.operational_spec import (
    Criterion,
    OperationalSpec,
    SpecStructure,
    StructureNode,
)
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.domain.strategy.spec_diff import CriterionChange
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService


def _never_factory() -> AsyncSession:
    msg = "db factory should not be called in unit tests"
    raise AssertionError(msg)


def _text_criterion() -> Criterion:
    return Criterion(
        id="step_text",
        text="genes matching protease",
        search_name="GenesByText",
    )


def _go_criterion(organism: str = "Plasmodium") -> Criterion:
    return Criterion(
        id="step_go",
        text="genes annotated with protein kinase activity",
        search_name="GenesByGoTerm",
        resolved_params={"organism": MultiPickValue(values=[organism])},
    )


def _expression_criterion(percentile: float = 80) -> Criterion:
    return Criterion(
        id="step_expr",
        text="genes in the top expression decile",
        search_name="GenesByRNASeqEvidence",
        resolved_params={"min_expression_percentile": NumberValue(value=percentile)},
    )


def _spec(*criteria: Criterion) -> OperationalSpec:
    return OperationalSpec(
        goal="find kinases",
        criteria=list(criteria),
        structure=SpecStructure(
            root=StructureNode(
                kind="combine",
                operator=CombineOp.INTERSECT,
                inputs=[
                    StructureNode(kind="leaf", criterion_id=c.id) for c in criteria
                ],
            )
        ),
    )


def _three() -> OperationalSpec:
    return _spec(_text_criterion(), _go_criterion(), _expression_criterion())


def _deps(before: OperationalSpec) -> LeadDeps:
    state = PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
        user_prompt="use the DeRisi dataset for the expression filter, keep the rest",
        domain=StrategyDomainState(
            operational_spec=before.model_copy(deep=True),
            spec_before_turn=before.model_copy(deep=True),
        ),
    )
    runtime = Context(
        site_id="plasmodb",
        user_id=uuid4(),
        strategy_session=StrategySession(site_id="plasmodb"),
        db_session_factory=_never_factory,
        web_search_service=WebSearchService(),
        literature_search_service=LiteratureSearchService(),
        cancel_event=asyncio.Event(),
    )
    return LeadDeps(state=state, intent=None, runtime=runtime, retrieved_memories=[])


def _stub_frame(
    monkeypatch: Any,
    after: OperationalSpec,
    changes: list[CriterionChange],
) -> None:
    """Drive one FRAME dispatch that leaves ``after`` in the shared draft."""

    async def _fake(**kwargs: Any) -> FrameResult:
        agent_deps: AgentDeps = kwargs["agent_deps"]
        agent_deps.agent_state.operational_spec_draft = after.model_copy(deep=True)
        return FrameResult(disposition="spec_ready", summary="edited", changes=changes)

    monkeypatch.setattr(sub_agent_dispatch, "stream_sub_agent", _fake)


async def test_undeclared_drop_is_a_retry(monkeypatch: Any) -> None:
    after = _spec(_text_criterion(), _go_criterion())
    _stub_frame(
        monkeypatch,
        after,
        [
            CriterionChange(criterion_id="step_text", disposition="kept"),
            CriterionChange(criterion_id="step_go", disposition="kept"),
        ],
    )

    with pytest.raises(ModelRetry) as excinfo:
        await run_frame(
            deps=_deps(_three()),
            parent_tool_call_id="t1",
            work_order=frame_work_order("edit", ""),
        )

    assert "step_expr" in str(excinfo.value)


async def test_declared_drop_passes(monkeypatch: Any) -> None:
    after = _spec(_text_criterion(), _go_criterion())
    _stub_frame(
        monkeypatch,
        after,
        [
            CriterionChange(criterion_id="step_text", disposition="kept"),
            CriterionChange(criterion_id="step_go", disposition="kept"),
            CriterionChange(
                criterion_id="step_expr",
                disposition="dropped",
                reason="the user asked for it to go",
            ),
        ],
    )

    result = await run_frame(
        deps=_deps(_three()),
        parent_tool_call_id="t1",
        work_order=frame_work_order("edit", ""),
    )

    assert isinstance(result, FrameResult)
    assert result.disposition == "spec_ready"


async def test_kept_criterion_keeps_its_values(monkeypatch: Any) -> None:
    after = _spec(
        _text_criterion(),
        _go_criterion(organism="Plasmodium falciparum 3D7"),
        _expression_criterion(),
    )
    _stub_frame(
        monkeypatch,
        after,
        [
            CriterionChange(criterion_id="step_text", disposition="kept"),
            CriterionChange(criterion_id="step_go", disposition="kept"),
            CriterionChange(criterion_id="step_expr", disposition="kept"),
        ],
    )

    with pytest.raises(ModelRetry) as excinfo:
        await run_frame(
            deps=_deps(_three()),
            parent_tool_call_id="t1",
            work_order=frame_work_order("edit", ""),
        )

    message = str(excinfo.value)
    assert "step_go" in message
    assert "Plasmodium falciparum 3D7" in message


async def test_a_declared_change_passes(monkeypatch: Any) -> None:
    after = _spec(_text_criterion(), _go_criterion(), _expression_criterion(90))
    _stub_frame(
        monkeypatch,
        after,
        [
            CriterionChange(criterion_id="step_text", disposition="kept"),
            CriterionChange(criterion_id="step_go", disposition="kept"),
            CriterionChange(
                criterion_id="step_expr",
                disposition="changed",
                changed_params={"min_expression_percentile": "90"},
            ),
        ],
    )

    result = await run_frame(
        deps=_deps(_three()),
        parent_tool_call_id="t1",
        work_order=frame_work_order("edit", ""),
    )

    assert isinstance(result, FrameResult)
    assert result.disposition == "spec_ready"


async def test_a_fresh_build_declares_nothing_and_passes(monkeypatch: Any) -> None:
    """No spec before the turn means there is nothing to preserve."""
    after = _spec(_text_criterion())
    _stub_frame(monkeypatch, after, [])
    deps = _deps(_three())
    deps.state.domain.spec_before_turn = None

    result = await run_frame(
        deps=deps, parent_tool_call_id="t1", work_order=frame_work_order("build", "")
    )

    assert isinstance(result, FrameResult)
    assert result.disposition == "spec_ready"


async def test_the_filed_measurement_is_rejected(monkeypatch: Any) -> None:
    """Three criteria in, two out, nothing declared dropped: a retry.

    The filed run asked to change only the expression dataset and came back
    with two of three criteria and a reply that said the rest was preserved.
    """
    after = _spec(_text_criterion(), _expression_criterion(90))
    _stub_frame(
        monkeypatch,
        after,
        [
            CriterionChange(
                criterion_id="step_expr",
                disposition="changed",
                changed_params={"min_expression_percentile": "90"},
            )
        ],
    )

    with pytest.raises(ModelRetry) as excinfo:
        await run_frame(
            deps=_deps(_three()),
            parent_tool_call_id="t1",
            work_order=frame_work_order("edit", ""),
        )

    message = str(excinfo.value)
    assert "step_go" in message
    assert "protein kinase activity" in message


async def test_a_refused_edit_leaves_the_spec_as_the_turn_found_it(
    monkeypatch: Any,
) -> None:
    """The retry's workspace must still show the criterion it has to preserve."""
    after = _spec(_text_criterion(), _go_criterion())
    _stub_frame(
        monkeypatch,
        after,
        [CriterionChange(criterion_id="step_text", disposition="kept")],
    )
    deps = _deps(_three())

    with pytest.raises(ModelRetry):
        await run_frame(
            deps=deps, parent_tool_call_id="t1", work_order=frame_work_order("edit", "")
        )

    spec = deps.state.domain.operational_spec
    assert spec is not None
    assert {c.id for c in spec.criteria} == {"step_text", "step_go", "step_expr"}

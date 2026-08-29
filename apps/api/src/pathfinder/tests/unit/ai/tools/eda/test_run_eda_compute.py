"""run_eda_compute defers the work and suspends the graph."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

import pytest
from langgraph.errors import GraphInterrupt
from langgraph.types import Interrupt
from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import RunContext
from pydantic_ai.usage import RunUsage
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.graph.state import PipelineState, StrategyDomainState
from pathfinder.ai.lead.sub_agent_tools import LeadDeps
from pathfinder.ai.tools import durable
from pathfinder.ai.tools.standalone import eda_compute
from pathfinder.ai.tools.standalone.eda_compute import EdaVariableSpecIn
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.jobs.impls import register_all_tools
from pathfinder.jobs.registry import TOOL_REGISTRY
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService


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
        user_prompt="which genes respond to fever",
        domain=StrategyDomainState(),
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
    deps = LeadDeps(state=state, intent=None, runtime=runtime, retrieved_memories=[])
    return RunContext(deps=deps, model=TestModel(), usage=RunUsage(), messages=[])


class _Task:
    def __init__(self, deferred: list[dict[str, Any]]) -> None:
        self._deferred = deferred

    async def defer_async(self, **payload: Any) -> None:
        self._deferred.append(payload)


class _App:
    def __init__(self, deferred: list[dict[str, Any]]) -> None:
        self._deferred = deferred

    def configure_task(self, *, name: str, queue: str, lock: str) -> _Task:
        del name, queue, lock
        return _Task(self._deferred)


def _raise_interrupt(payload: Any) -> Any:
    raise GraphInterrupt((Interrupt(value=payload),))


@pytest.fixture
def dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """Capture what the decorator creates and defers, without a graph or a db."""
    created: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []

    async def create(**kwargs: Any) -> Any:
        created.append(dict(kwargs))
        return uuid4()

    monkeypatch.setattr(durable, "create_background_task", create)
    monkeypatch.setattr(durable, "procrastinate_app", _App(deferred))
    monkeypatch.setattr(durable, "interrupt", _raise_interrupt)
    return created, deferred


async def test_calling_the_tool_creates_a_task_and_defers_a_job(
    lead_ctx: RunContext[LeadDeps],
    dispatch: tuple[list[dict[str, Any]], list[dict[str, Any]]],
) -> None:
    created, deferred = dispatch

    with pytest.raises(GraphInterrupt):
        await eda_compute.run_eda_compute(
            lead_ctx,
            identifier_variable=EdaVariableSpecIn(
                entity_id="ENT_fd574cd6",
                variable_id="VEUPATHDB_GENE_ID",
            ),
            value_variable=EdaVariableSpecIn(
                entity_id="ENT_fd574cd6",
                variable_id="SEQUENCE_READ_COUNT_SENSE",
            ),
            comparator_variable=EdaVariableSpecIn(
                entity_id="ENT_8151325d",
                variable_id="VAR_081ab087",
            ),
            group_a_labels=["normal"],
            group_b_labels=["febrile"],
        )

    assert [entry["tool_name"] for entry in created] == ["run_eda_compute"]
    assert created[0]["conversation_id"] == lead_ctx.deps.state.conversation_id
    assert created[0]["user_id"] == lead_ctx.deps.runtime.user_id
    assert len(deferred) == 1
    assert deferred[0]["thread_id"] == str(lead_ctx.deps.state.conversation_id)


async def test_the_deferred_job_carries_the_arguments_the_impl_needs(
    lead_ctx: RunContext[LeadDeps],
    dispatch: tuple[list[dict[str, Any]], list[dict[str, Any]]],
) -> None:
    created, _deferred = dispatch

    with pytest.raises(GraphInterrupt):
        await eda_compute.run_eda_compute(
            lead_ctx,
            identifier_variable=EdaVariableSpecIn(
                entity_id="E",
                variable_id="VEUPATHDB_GENE_ID",
            ),
            value_variable=EdaVariableSpecIn(
                entity_id="E",
                variable_id="SEQUENCE_READ_COUNT",
            ),
            comparator_variable=EdaVariableSpecIn(entity_id="P", variable_id="C"),
            group_a_labels=["a"],
            group_b_labels=["b"],
            method="limma",
        )

    kwargs = created[0]["args"]["kwargs"]
    assert kwargs["method"] == "limma"
    assert kwargs["group_a_labels"] == ["a"]
    assert kwargs["group_b_labels"] == ["b"]
    assert kwargs["identifier_variable"] == {
        "entity_id": "E",
        "variable_id": "VEUPATHDB_GENE_ID",
    }
    assert kwargs["comparator_variable"] == {"entity_id": "P", "variable_id": "C"}


async def test_the_estimated_duration_is_declared(
    lead_ctx: RunContext[LeadDeps],
    dispatch: tuple[list[dict[str, Any]], list[dict[str, Any]]],
) -> None:
    created, _deferred = dispatch

    with pytest.raises(GraphInterrupt):
        await eda_compute.run_eda_compute(
            lead_ctx,
            identifier_variable=EdaVariableSpecIn(
                entity_id="E",
                variable_id="VEUPATHDB_GENE_ID",
            ),
            value_variable=EdaVariableSpecIn(
                entity_id="E",
                variable_id="SEQUENCE_READ_COUNT",
            ),
            comparator_variable=EdaVariableSpecIn(entity_id="P", variable_id="C"),
            group_a_labels=["a"],
            group_b_labels=["b"],
        )

    assert created[0]["estimated_duration_seconds"] == 120


def test_the_tool_is_registered_in_the_worker_registry() -> None:
    register_all_tools()
    assert "run_eda_compute" in TOOL_REGISTRY

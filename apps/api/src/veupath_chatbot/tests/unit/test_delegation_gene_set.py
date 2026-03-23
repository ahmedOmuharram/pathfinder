"""Tests for automatic gene set creation after successful delegation.

Verifies that delegate_strategy_subtasks() includes a geneSetCreated
payload in its result when sub-kani tasks complete with valid steps,
and that the event extractor pipeline picks it up.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from veupath_chatbot.ai.orchestration.delegation import DelegationPlan
from veupath_chatbot.ai.orchestration.subkani.orchestrator import (
    delegate_strategy_subtasks,
)
from veupath_chatbot.ai.orchestration.types import SubkaniContext
from veupath_chatbot.services.chat.events import (
    EventType,
    tool_result_to_events,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_SITE_ID = "plasmodb"
_FAKE_GRAPH_ID = "graph-001"
_FAKE_GRAPH_NAME = "Test Strategy"


def _make_strategy_session(
    graph_id: str = _FAKE_GRAPH_ID,
    site_id: str = _FAKE_SITE_ID,
) -> MagicMock:
    """Create a minimal mock StrategySession."""
    graph = MagicMock()
    graph.id = graph_id
    graph.name = _FAKE_GRAPH_NAME
    graph.site_id = site_id
    graph.roots = set()
    graph.steps = {}
    graph.current_strategy = MagicMock()
    graph.current_strategy.name = _FAKE_GRAPH_NAME
    graph.current_strategy.description = "Test"

    session = MagicMock()
    session.site_id = site_id
    session.get_graph = MagicMock(return_value=graph)
    session.create_graph = MagicMock(return_value=graph)
    return session


def _make_delegation_plan(tasks: list[dict[str, Any]]) -> DelegationPlan:
    """Build a real DelegationPlan for testing."""
    nodes_by_id = {t.get("id", f"t{i}"): t for i, t in enumerate(tasks)}
    dependents = {tid: [] for tid in nodes_by_id}
    return DelegationPlan(
        goal="test",
        tasks=tasks,
        combines=[],
        nodes_by_id=nodes_by_id,
        dependents=dependents,
    )


def _make_task_result(task: str, step_id: str = "step-1") -> dict[str, Any]:
    """Successful sub-kani task result."""
    return {
        "id": "t0",
        "task": task,
        "kind": "task",
        "steps": [{"stepId": step_id, "graphId": _FAKE_GRAPH_ID}],
        "notes": "created",
    }


# ---------------------------------------------------------------------------
# Test: event extractor picks up geneSetCreated from delegation-like result
# ---------------------------------------------------------------------------


class TestEventExtractorPicksUpGeneSetFromDelegation:
    """The _extract_gene_set_created extractor handles delegation results."""

    def test_delegation_result_with_gene_set_created_emits_event(self) -> None:
        """A delegation result dict containing geneSetCreated triggers the event."""
        gene_set_payload = {
            "id": "gs-123",
            "name": "Test Strategy",
            "geneCount": 0,
            "source": "strategy",
            "siteId": "plasmodb",
        }
        delegation_result = {
            "goal": "Find kinase genes",
            "graphId": _FAKE_GRAPH_ID,
            "graphName": _FAKE_GRAPH_NAME,
            "results": [_make_task_result("Find kinases")],
            "rejected": [],
            "geneSetCreated": gene_set_payload,
        }
        events = tool_result_to_events(delegation_result)
        gs_events = [e for e in events if e.get("type") == EventType.WORKBENCH_GENE_SET]
        assert len(gs_events) == 1
        event_data = gs_events[0].get("data")
        assert isinstance(event_data, dict)
        assert event_data.get("geneSet") == gene_set_payload

    def test_delegation_result_without_gene_set_created_no_event(self) -> None:
        """Without geneSetCreated, no workbench_gene_set event is emitted."""
        delegation_result = {
            "goal": "Find kinase genes",
            "graphId": _FAKE_GRAPH_ID,
            "graphName": _FAKE_GRAPH_NAME,
            "results": [_make_task_result("Find kinases")],
            "rejected": [],
        }
        events = tool_result_to_events(delegation_result)
        gs_events = [e for e in events if e.get("type") == EventType.WORKBENCH_GENE_SET]
        assert len(gs_events) == 0


# ---------------------------------------------------------------------------
# Test: delegate_strategy_subtasks includes geneSetCreated
# ---------------------------------------------------------------------------


class TestDelegationGeneSetCreation:
    """delegate_strategy_subtasks no longer creates gene sets internally.

    Gene-set creation was moved out of the orchestrator.  These tests verify
    that the delegation result contains the expected structure (results,
    rejected, graphName, etc.) and does NOT include a ``geneSetCreated`` key.
    """

    @pytest.mark.asyncio
    async def test_delegation_result_has_correct_structure(self) -> None:
        """When delegation succeeds with valid steps, result has expected keys."""
        task = {"id": "t0", "task": "Find kinases", "kind": "task"}
        plan = _make_delegation_plan([task])
        session = _make_strategy_session()
        emit = AsyncMock()
        strategy_tools = MagicMock()
        strategy_tools._build_graph_snapshot = MagicMock(return_value={"steps": []})

        task_result = _make_task_result("Find kinases")

        with (
            patch(
                "veupath_chatbot.ai.orchestration.subkani.orchestrator.build_delegation_plan",
                return_value=plan,
            ),
            patch(
                "veupath_chatbot.ai.orchestration.subkani.orchestrator.run_nodes_with_dependencies",
                new_callable=AsyncMock,
                return_value=([task_result], {"t0": task_result}),
            ),
            patch(
                "veupath_chatbot.ai.orchestration.subkani.orchestrator.partition_task_results",
                return_value=([task_result], []),
            ),
            patch(
                "veupath_chatbot.ai.orchestration.subkani.orchestrator.derive_graph_metadata",
                return_value=(_FAKE_GRAPH_NAME, "Test description"),
            ),
        ):
            result = await delegate_strategy_subtasks(
                goal="Find kinase genes",
                context=SubkaniContext(
                    site_id=_FAKE_SITE_ID,
                    strategy_session=session,
                    chat_history=[],
                    emit_event=emit,
                    subkani_timeout_seconds=0,
                ),
                strategy_tools=strategy_tools,
            )

        # Gene-set creation is no longer part of delegation
        assert "geneSetCreated" not in result

        # Core result shape
        assert result["goal"] == "Find kinase genes"
        assert result["graphName"] == _FAKE_GRAPH_NAME
        assert result["results"] == [task_result]
        assert result["rejected"] == []

    @pytest.mark.asyncio
    async def test_delegation_result_no_gene_set_when_no_validated(self) -> None:
        """When delegation has no validated results, no gene set key appears."""
        task = {"id": "t0", "task": "Find kinases", "kind": "task"}
        plan = _make_delegation_plan([task])
        session = _make_strategy_session()
        emit = AsyncMock()
        strategy_tools = MagicMock()
        strategy_tools._build_graph_snapshot = MagicMock(return_value={"steps": []})

        rejected_result = {
            "id": "t0",
            "task": "Find kinases",
            "kind": "task",
            "steps": [],
            "notes": "no_steps",
        }

        with (
            patch(
                "veupath_chatbot.ai.orchestration.subkani.orchestrator.build_delegation_plan",
                return_value=plan,
            ),
            patch(
                "veupath_chatbot.ai.orchestration.subkani.orchestrator.run_nodes_with_dependencies",
                new_callable=AsyncMock,
                return_value=([rejected_result], {"t0": rejected_result}),
            ),
            patch(
                "veupath_chatbot.ai.orchestration.subkani.orchestrator.partition_task_results",
                return_value=([], [rejected_result]),
            ),
            patch(
                "veupath_chatbot.ai.orchestration.subkani.orchestrator.derive_graph_metadata",
                return_value=(_FAKE_GRAPH_NAME, "Test description"),
            ),
        ):
            result = await delegate_strategy_subtasks(
                goal="Find kinase genes",
                context=SubkaniContext(
                    site_id=_FAKE_SITE_ID,
                    strategy_session=session,
                    chat_history=[],
                    emit_event=emit,
                    subkani_timeout_seconds=0,
                ),
                strategy_tools=strategy_tools,
            )

        assert "geneSetCreated" not in result
        assert result["results"] == []
        assert result["rejected"] == [rejected_result]

    @pytest.mark.asyncio
    async def test_delegation_result_contains_graph_metadata(self) -> None:
        """Delegation result includes graphName and graphDescription from derive_graph_metadata."""
        task = {"id": "t0", "task": "Find kinases", "kind": "task"}
        plan = _make_delegation_plan([task])
        session = _make_strategy_session()
        emit = AsyncMock()
        strategy_tools = MagicMock()
        strategy_tools._build_graph_snapshot = MagicMock(return_value={"steps": []})

        task_result = _make_task_result("Find kinases")

        with (
            patch(
                "veupath_chatbot.ai.orchestration.subkani.orchestrator.build_delegation_plan",
                return_value=plan,
            ),
            patch(
                "veupath_chatbot.ai.orchestration.subkani.orchestrator.run_nodes_with_dependencies",
                new_callable=AsyncMock,
                return_value=([task_result], {"t0": task_result}),
            ),
            patch(
                "veupath_chatbot.ai.orchestration.subkani.orchestrator.partition_task_results",
                return_value=([task_result], []),
            ),
            patch(
                "veupath_chatbot.ai.orchestration.subkani.orchestrator.derive_graph_metadata",
                return_value=(_FAKE_GRAPH_NAME, "Test description"),
            ),
        ):
            result = await delegate_strategy_subtasks(
                goal="Find kinase genes",
                context=SubkaniContext(
                    site_id=_FAKE_SITE_ID,
                    strategy_session=session,
                    chat_history=[],
                    emit_event=emit,
                    subkani_timeout_seconds=0,
                ),
                strategy_tools=strategy_tools,
            )

        assert result["graphName"] == _FAKE_GRAPH_NAME
        assert result["graphDescription"] == "Test description"
        assert "graphId" in result

    @pytest.mark.asyncio
    async def test_delegation_does_not_accept_user_id(self) -> None:
        """delegate_strategy_subtasks no longer accepts a user_id parameter."""
        task = {"id": "t0", "task": "Find kinases", "kind": "task"}
        plan = _make_delegation_plan([task])
        session = _make_strategy_session()
        emit = AsyncMock()
        strategy_tools = MagicMock()
        strategy_tools._build_graph_snapshot = MagicMock(return_value={"steps": []})

        task_result = _make_task_result("Find kinases")

        with (
            patch(
                "veupath_chatbot.ai.orchestration.subkani.orchestrator.build_delegation_plan",
                return_value=plan,
            ),
            patch(
                "veupath_chatbot.ai.orchestration.subkani.orchestrator.run_nodes_with_dependencies",
                new_callable=AsyncMock,
                return_value=([task_result], {"t0": task_result}),
            ),
            patch(
                "veupath_chatbot.ai.orchestration.subkani.orchestrator.partition_task_results",
                return_value=([task_result], []),
            ),
            patch(
                "veupath_chatbot.ai.orchestration.subkani.orchestrator.derive_graph_metadata",
                return_value=(_FAKE_GRAPH_NAME, "Test description"),
            ),
            pytest.raises(TypeError, match="user_id"),
        ):
            await delegate_strategy_subtasks(
                goal="Find kinase genes",
                context=SubkaniContext(
                    site_id=_FAKE_SITE_ID,
                    strategy_session=session,
                    chat_history=[],
                    emit_event=emit,
                    subkani_timeout_seconds=0,
                ),
                strategy_tools=strategy_tools,
                user_id=None,  # type: ignore[call-arg]
            )

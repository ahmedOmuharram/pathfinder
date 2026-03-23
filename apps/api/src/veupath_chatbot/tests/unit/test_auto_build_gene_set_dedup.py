"""Tests for auto-build gene set deduplication (one gene set per conversation).

Flow 1: First build — no gene_set_id on projection → create + link.
Flow 2: Rebuild — projection has gene_set_id → update existing gene set.
Flow 3: Rebuild after deletion — gene_set_id is NULL (user deleted) → create + link.
Flow 4: Auto-import already linked — auto-build reuses the auto-imported gene set.
Flow 5: AI explicit create_workbench_gene_set — standalone, not linked to projection.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from kani import ChatMessage
from kani.internal import FunctionCallResult
from kani.models import FunctionCall

from veupath_chatbot.ai.agents.executor import AgentContext, PathfinderAgent
from veupath_chatbot.ai.engines.mock import MockEngine
from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.services.gene_sets.types import GeneSet
from veupath_chatbot.services.strategies.sync import SyncResult

_USER_ID = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
_SITE_ID = "plasmodb"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent(
    *,
    site_id: str = _SITE_ID,
    user_id: UUID | None = _USER_ID,
    stream_id: str | None = None,
) -> PathfinderAgent:
    """Create a PathfinderAgent with a MockEngine, event queue, and user_id."""
    agent = PathfinderAgent(
        engine=MockEngine(site_id=site_id),
        context=AgentContext(site_id=site_id, user_id=user_id),
    )
    agent.event_queue = asyncio.Queue()
    return agent


def _step(step_id: str = "s1") -> PlanStepNode:
    return PlanStepNode(
        search_name="GenesByTaxon",
        parameters={"organism": '["Plasmodium falciparum 3D7"]'},
        id=step_id,
    )


def _tool_result_json(step_id: str = "s1") -> str:
    return json.dumps(
        {
            "ok": True,
            "stepId": step_id,
            "kind": "search",
            "displayName": "All genes",
            "graphSnapshot": {
                "graphId": "g1",
                "steps": [{"id": step_id, "kind": "search"}],
                "rootStepId": step_id,
            },
        }
    )


def _sync_result(wdk_strategy_id: int = 999) -> SyncResult:
    return SyncResult(
        wdk_strategy_id=wdk_strategy_id,
        wdk_url=f"https://plasmodb.org/plasmo/app/workspace/strategies/{wdk_strategy_id}",
        root_step_id=100,
        root_count=42,
        step_count=1,
        counts={"s1": 42},
        zero_step_ids=[],
    )


def _parent_result(content: str = "") -> FunctionCallResult:
    msg = ChatMessage.function("create_step", content or _tool_result_json())
    return FunctionCallResult(is_model_turn=True, message=msg)


def _make_gene_set(
    gene_set_id: str | None = None,
    name: str = "Test Strategy",
    wdk_strategy_id: int | None = 999,
) -> GeneSet:
    return GeneSet(
        id=gene_set_id or str(uuid4()),
        name=name,
        site_id=_SITE_ID,
        gene_ids=["PF3D7_0000001", "PF3D7_0000002"],
        source="strategy",
        user_id=_USER_ID,
        wdk_strategy_id=wdk_strategy_id,
    )


def _setup_agent_with_graph(agent: PathfinderAgent) -> None:
    """Add a single-root graph to trigger auto-build."""
    graph = agent.strategy_session.get_graph(None)
    assert graph is not None
    graph.add_step(_step("s1"))
    graph.record_type = "gene"


def _drain_events(agent: PathfinderAgent) -> list[dict]:
    events = []
    while not agent.event_queue.empty():
        events.append(agent.event_queue.get_nowait())
    return events


def _gene_set_events(events: list[dict]) -> list[dict]:
    """Extract geneSetCreated from auto-build results in tool content."""
    return [e for e in events if e.get("type") == "workbench_gene_set"]


# ---------------------------------------------------------------------------
# Flow 1: First build in a new conversation
# ---------------------------------------------------------------------------


class TestFirstBuildCreatesGeneSet:
    """When the projection has no gene_set_id, auto-build creates a new
    gene set and links it to the projection."""

    @pytest.fixture
    def agent(self) -> PathfinderAgent:
        agent = _make_agent()
        _setup_agent_with_graph(agent)
        return agent

    async def test_first_build_creates_one_gene_set(self, agent):
        """Auto-build on first graph mutation creates exactly one gene set."""
        created_gs = _make_gene_set()
        mock_svc = MagicMock()
        mock_svc.create = AsyncMock(return_value=created_gs)
        mock_svc.flush = AsyncMock()
        mock_svc.find_by_wdk_strategy = MagicMock(return_value=None)
        mock_store = MagicMock()
        mock_store.get = MagicMock(return_value=None)

        call = FunctionCall(name="create_step", arguments="{}")

        with (
            patch("kani.Kani.do_function_call", return_value=_parent_result()),
            patch(
                "veupath_chatbot.ai.agents.executor.sync_strategy_for_site",
                return_value=_sync_result(),
            ),
            patch(
                "veupath_chatbot.ai.agents.executor.GeneSetService",
                return_value=mock_svc,
            ),
            patch(
                "veupath_chatbot.ai.agents.executor.get_gene_set_store",
                return_value=mock_store,
            ),
        ):
            result = await agent.do_function_call(call, "tc1")

        parsed = json.loads(result.message.text)
        assert "autoBuild" in parsed
        assert parsed["autoBuild"]["ok"] is True
        # Gene set must be created
        assert "geneSetCreated" in parsed["autoBuild"]
        assert parsed["autoBuild"]["geneSetCreated"]["id"] == created_gs.id

    async def test_first_build_calls_create_not_update(self, agent):
        """First build must call svc.create(), not just save() on an existing set."""
        created_gs = _make_gene_set()
        mock_svc = MagicMock()
        mock_svc.create = AsyncMock(return_value=created_gs)
        mock_svc.flush = AsyncMock()
        mock_svc.find_by_wdk_strategy = MagicMock(return_value=None)
        mock_store = MagicMock()
        mock_store.get = MagicMock(return_value=None)

        call = FunctionCall(name="create_step", arguments="{}")

        with (
            patch("kani.Kani.do_function_call", return_value=_parent_result()),
            patch(
                "veupath_chatbot.ai.agents.executor.sync_strategy_for_site",
                return_value=_sync_result(),
            ),
            patch(
                "veupath_chatbot.ai.agents.executor.GeneSetService",
                return_value=mock_svc,
            ),
            patch(
                "veupath_chatbot.ai.agents.executor.get_gene_set_store",
                return_value=mock_store,
            ),
        ):
            await agent.do_function_call(call, "tc1")

        mock_svc.create.assert_called_once()


# ---------------------------------------------------------------------------
# Flow 2: Rebuild — same conversation, graph mutated again
# ---------------------------------------------------------------------------


class TestRebuildReusesExistingGeneSet:
    """When auto-build fires again for the same conversation (graph mutation),
    it must reuse the existing gene set, not create a duplicate."""

    @pytest.fixture
    def agent(self) -> PathfinderAgent:
        agent = _make_agent()
        _setup_agent_with_graph(agent)
        return agent

    async def test_second_build_reuses_gene_set_by_wdk_strategy_id(self, agent):
        """When a gene set already exists for the wdk_strategy_id, reuse it."""
        existing_gs = _make_gene_set(gene_set_id="existing-gs-id", wdk_strategy_id=999)
        mock_svc = MagicMock()
        mock_svc.create = AsyncMock()
        mock_svc.flush = AsyncMock()
        mock_svc.find_by_wdk_strategy = MagicMock(return_value=existing_gs)
        mock_store = MagicMock()
        mock_store.get = MagicMock(return_value=None)
        mock_store.save = MagicMock()

        call = FunctionCall(name="create_step", arguments="{}")

        with (
            patch("kani.Kani.do_function_call", return_value=_parent_result()),
            patch(
                "veupath_chatbot.ai.agents.executor.sync_strategy_for_site",
                return_value=_sync_result(wdk_strategy_id=999),
            ),
            patch(
                "veupath_chatbot.ai.agents.executor.GeneSetService",
                return_value=mock_svc,
            ),
            patch(
                "veupath_chatbot.ai.agents.executor.get_gene_set_store",
                return_value=mock_store,
            ),
        ):
            result = await agent.do_function_call(call, "tc1")

        parsed = json.loads(result.message.text)
        # Must reuse existing, NOT create new
        mock_svc.create.assert_not_called()
        assert parsed["autoBuild"]["geneSetCreated"]["id"] == "existing-gs-id"

    async def test_three_consecutive_builds_produce_one_gene_set(self, agent):
        """Three graph mutations in the same session must all reference the
        same gene set — no accumulation of duplicates."""
        gs_id = "the-one-gene-set"
        existing_gs = _make_gene_set(gene_set_id=gs_id, wdk_strategy_id=999)

        mock_svc = MagicMock()
        mock_svc.create = AsyncMock(return_value=existing_gs)
        mock_svc.flush = AsyncMock()
        # First call: nothing exists yet. Second+: find the one we created.
        mock_svc.find_by_wdk_strategy = MagicMock(
            side_effect=[None, existing_gs, existing_gs]
        )
        mock_store = MagicMock()
        mock_store.get = MagicMock(side_effect=[None, existing_gs, existing_gs])
        mock_store.save = MagicMock()

        call = FunctionCall(name="create_step", arguments="{}")

        with (
            patch("kani.Kani.do_function_call", return_value=_parent_result()),
            patch(
                "veupath_chatbot.ai.agents.executor.sync_strategy_for_site",
                return_value=_sync_result(wdk_strategy_id=999),
            ),
            patch(
                "veupath_chatbot.ai.agents.executor.GeneSetService",
                return_value=mock_svc,
            ),
            patch(
                "veupath_chatbot.ai.agents.executor.get_gene_set_store",
                return_value=mock_store,
            ),
        ):
            for _ in range(3):
                result = await agent.do_function_call(call, "tc1")

        # Only 1 create call (the first one)
        mock_svc.create.assert_called_once()
        # All three results should reference the same gene set
        parsed = json.loads(result.message.text)
        assert parsed["autoBuild"]["geneSetCreated"]["id"] == gs_id


# ---------------------------------------------------------------------------
# Flow 3: Rebuild after user deleted the gene set
# ---------------------------------------------------------------------------


class TestRebuildAfterDeletion:
    """When the user deletes the gene set and then the graph changes,
    a new gene set should be created."""

    @pytest.fixture
    def agent(self) -> PathfinderAgent:
        agent = _make_agent()
        _setup_agent_with_graph(agent)
        return agent

    async def test_rebuild_after_deletion_creates_new_gene_set(self, agent):
        """If the old gene set was deleted (find_by_wdk_strategy returns None),
        auto-build creates a fresh gene set."""
        new_gs = _make_gene_set(gene_set_id="new-after-delete")
        mock_svc = MagicMock()
        mock_svc.create = AsyncMock(return_value=new_gs)
        mock_svc.flush = AsyncMock()
        # Nothing found — previous gene set was deleted
        mock_svc.find_by_wdk_strategy = MagicMock(return_value=None)
        mock_store = MagicMock()
        mock_store.get = MagicMock(return_value=None)

        call = FunctionCall(name="create_step", arguments="{}")

        with (
            patch("kani.Kani.do_function_call", return_value=_parent_result()),
            patch(
                "veupath_chatbot.ai.agents.executor.sync_strategy_for_site",
                return_value=_sync_result(wdk_strategy_id=999),
            ),
            patch(
                "veupath_chatbot.ai.agents.executor.GeneSetService",
                return_value=mock_svc,
            ),
            patch(
                "veupath_chatbot.ai.agents.executor.get_gene_set_store",
                return_value=mock_store,
            ),
        ):
            result = await agent.do_function_call(call, "tc1")

        mock_svc.create.assert_called_once()
        parsed = json.loads(result.message.text)
        assert parsed["autoBuild"]["geneSetCreated"]["id"] == "new-after-delete"

    async def test_no_gene_set_created_when_graph_unchanged(self):
        """If the user deleted the gene set but no graph mutation happens,
        no gene set is recreated (auto-build only fires on graph tools)."""
        agent = _make_agent()
        _setup_agent_with_graph(agent)

        # Non-graph-mutating tool — should NOT trigger auto-build at all
        call = FunctionCall(name="search_for_searches", arguments="{}")

        with patch("kani.Kani.do_function_call", return_value=_parent_result()):
            result = await agent.do_function_call(call, "tc1")

        parsed = json.loads(result.message.text)
        assert "autoBuild" not in parsed


# ---------------------------------------------------------------------------
# Flow 4: Auto-import already linked a gene set, then auto-build fires
# ---------------------------------------------------------------------------


class TestAutoBuildWithAutoImportedGeneSet:
    """If auto-import already created and linked a gene set for this strategy,
    auto-build should reuse it via find_by_wdk_strategy."""

    async def test_auto_build_reuses_auto_imported_gene_set(self):
        """Auto-build finds the auto-imported gene set and reuses it."""
        agent = _make_agent()
        _setup_agent_with_graph(agent)

        imported_gs = _make_gene_set(
            gene_set_id="auto-imported-gs", wdk_strategy_id=999
        )
        mock_svc = MagicMock()
        mock_svc.create = AsyncMock()
        mock_svc.flush = AsyncMock()
        mock_svc.find_by_wdk_strategy = MagicMock(return_value=imported_gs)
        mock_store = MagicMock()
        mock_store.get = MagicMock(return_value=None)
        mock_store.save = MagicMock()

        call = FunctionCall(name="create_step", arguments="{}")

        with (
            patch("kani.Kani.do_function_call", return_value=_parent_result()),
            patch(
                "veupath_chatbot.ai.agents.executor.sync_strategy_for_site",
                return_value=_sync_result(wdk_strategy_id=999),
            ),
            patch(
                "veupath_chatbot.ai.agents.executor.GeneSetService",
                return_value=mock_svc,
            ),
            patch(
                "veupath_chatbot.ai.agents.executor.get_gene_set_store",
                return_value=mock_store,
            ),
        ):
            result = await agent.do_function_call(call, "tc1")

        mock_svc.create.assert_not_called()
        parsed = json.loads(result.message.text)
        assert parsed["autoBuild"]["geneSetCreated"]["id"] == "auto-imported-gs"


# ---------------------------------------------------------------------------
# Flow 5: WDK strategy ID changes (update failed, new strategy created)
# ---------------------------------------------------------------------------


class TestWdkStrategyIdChanges:
    """When WDK update fails and a new strategy ID is created, the old gene
    set should be updated with the new WDK ID — not a second gene set created."""

    async def test_wdk_id_change_updates_existing_gene_set(self):
        """If the WDK strategy ID changes but we have a tracked gene set
        from a prior build in this session, update it."""
        agent = _make_agent()
        _setup_agent_with_graph(agent)

        # First build: creates gene set with wdk_strategy_id=100
        first_gs = _make_gene_set(gene_set_id="gs-1", wdk_strategy_id=100)
        mock_svc = MagicMock()
        mock_svc.create = AsyncMock(return_value=first_gs)
        mock_svc.flush = AsyncMock()
        # Both calls: find_by_wdk_strategy returns None (first build has no
        # prior gene set; second build searches for NEW wdk_id=200 which
        # doesn't match gs-1's wdk_id=100).
        mock_svc.find_by_wdk_strategy = MagicMock(return_value=None)
        mock_store = MagicMock()
        # store.get is only called on the SECOND build (first build skips
        # because _auto_build_gene_set_id is None). On the second build,
        # store.get("gs-1") should find the gene set created by the first.
        mock_store.get = MagicMock(return_value=first_gs)
        mock_store.save = MagicMock()

        call = FunctionCall(name="create_step", arguments="{}")

        with (
            patch("kani.Kani.do_function_call", return_value=_parent_result()),
            patch(
                "veupath_chatbot.ai.agents.executor.sync_strategy_for_site",
                side_effect=[
                    _sync_result(wdk_strategy_id=100),
                    _sync_result(wdk_strategy_id=200),
                ],
            ),
            patch(
                "veupath_chatbot.ai.agents.executor.GeneSetService",
                return_value=mock_svc,
            ),
            patch(
                "veupath_chatbot.ai.agents.executor.get_gene_set_store",
                return_value=mock_store,
            ),
        ):
            # First build
            await agent.do_function_call(call, "tc1")
            # Second build — WDK ID changed from 100 to 200
            result = await agent.do_function_call(call, "tc2")

        # Only 1 create (the first build), second should reuse
        mock_svc.create.assert_called_once()
        parsed = json.loads(result.message.text)
        assert parsed["autoBuild"]["geneSetCreated"]["id"] == "gs-1"


# ---------------------------------------------------------------------------
# Flow 6: No user_id — skip gene set creation
# ---------------------------------------------------------------------------


class TestNoUserIdSkipsGeneSet:
    """Without a user_id, gene set creation should be skipped entirely."""

    async def test_no_gene_set_without_user_id(self):
        agent = _make_agent(user_id=None)
        _setup_agent_with_graph(agent)

        call = FunctionCall(name="create_step", arguments="{}")

        with (
            patch("kani.Kani.do_function_call", return_value=_parent_result()),
            patch(
                "veupath_chatbot.ai.agents.executor.sync_strategy_for_site",
                return_value=_sync_result(),
            ),
        ):
            result = await agent.do_function_call(call, "tc1")

        parsed = json.loads(result.message.text)
        assert "autoBuild" in parsed
        assert parsed["autoBuild"]["ok"] is True
        # No gene set should be created for anonymous users
        assert "geneSetCreated" not in parsed["autoBuild"]

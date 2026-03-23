"""Unit tests for the auto-build hook in PathfinderAgent.do_function_call.

Verifies that auto-build results are merged into the tool result as valid JSON
(not appended as text), and that appropriate events are emitted.
"""

import asyncio
import json
from unittest.mock import patch

import pytest
from kani import ChatMessage
from kani.internal import FunctionCallResult
from kani.models import FunctionCall

from veupath_chatbot.ai.agents.executor import AgentContext, PathfinderAgent
from veupath_chatbot.ai.engines.mock import MockEngine
from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.platform.errors import WDKError
from veupath_chatbot.platform.parsing import parse_jsonish
from veupath_chatbot.services.strategies.sync import SyncResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent(*, site_id: str = "plasmodb") -> PathfinderAgent:
    """Create a PathfinderAgent with a MockEngine and event queue."""
    agent = PathfinderAgent(
        engine=MockEngine(site_id=site_id),
        context=AgentContext(site_id=site_id),
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
    """Simulate a create_step tool result (valid JSON)."""
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
    """Create a successful SyncResult."""
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
    """Simulate the result of super().do_function_call."""
    msg = ChatMessage.function("create_step", content or _tool_result_json())
    return FunctionCallResult(is_model_turn=True, message=msg)


def _drain_queue(queue: asyncio.Queue) -> list[dict]:
    """Drain all events from a queue synchronously."""
    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    return events


# ---------------------------------------------------------------------------
# Tests: auto-build result is valid JSON
# ---------------------------------------------------------------------------


class TestAutoBuildResultFormat:
    """Auto-build must merge data into JSON, not append text."""

    @pytest.fixture
    def agent(self) -> PathfinderAgent:
        agent = _make_agent()
        # Set up graph with a single root (triggers auto-build).
        graph = agent.strategy_session.get_graph(None)
        assert graph is not None
        step = _step("s1")
        graph.add_step(step)
        graph.record_type = "gene"
        return agent

    async def test_auto_build_success_produces_valid_json(self, agent):
        """After successful auto-build, result.message.content is valid JSON."""
        call = FunctionCall(name="create_step", arguments="{}")

        with (
            patch("kani.Kani.do_function_call", return_value=_parent_result()),
            patch(
                "veupath_chatbot.ai.agents.executor.sync_strategy_for_site",
                return_value=_sync_result(),
            ),
            patch(
                "veupath_chatbot.ai.agents.executor.GeneSetService",
                side_effect=ImportError("skip"),
            ),
        ):
            result = await agent.do_function_call(call, "tc1")

        content = result.message.text
        # CRITICAL: content must be valid JSON, not text with appended suffix
        parsed = json.loads(content)
        assert isinstance(parsed, dict)
        assert "autoBuild" in parsed
        assert parsed["autoBuild"]["ok"] is True
        assert parsed["autoBuild"]["wdkStrategyId"] == 999

    async def test_auto_build_success_preserves_original_fields(self, agent):
        """Merged JSON still contains the original step fields."""
        call = FunctionCall(name="create_step", arguments="{}")

        with (
            patch("kani.Kani.do_function_call", return_value=_parent_result()),
            patch(
                "veupath_chatbot.ai.agents.executor.sync_strategy_for_site",
                return_value=_sync_result(),
            ),
            patch(
                "veupath_chatbot.ai.agents.executor.GeneSetService",
                side_effect=ImportError("skip"),
            ),
        ):
            result = await agent.do_function_call(call, "tc1")

        parsed = json.loads(result.message.text)
        assert parsed["ok"] is True
        assert parsed["stepId"] == "s1"
        assert "graphSnapshot" in parsed

    async def test_auto_build_failure_produces_valid_json(self, agent):
        """After failed auto-build, result.message.content is still valid JSON."""
        call = FunctionCall(name="create_step", arguments="{}")

        with (
            patch("kani.Kani.do_function_call", return_value=_parent_result()),
            patch(
                "veupath_chatbot.ai.agents.executor.sync_strategy_for_site",
                side_effect=WDKError("WDK rejected the strategy"),
            ),
        ):
            result = await agent.do_function_call(call, "tc1")

        content = result.message.text
        parsed = json.loads(content)
        assert isinstance(parsed, dict)
        assert "autoBuild" in parsed
        assert parsed["autoBuild"]["ok"] is False
        assert "WDK rejected" in parsed["autoBuild"]["error"]

    async def test_auto_build_failure_preserves_original_fields(self, agent):
        """Failed auto-build still preserves the original step fields."""
        call = FunctionCall(name="create_step", arguments="{}")

        with (
            patch("kani.Kani.do_function_call", return_value=_parent_result()),
            patch(
                "veupath_chatbot.ai.agents.executor.sync_strategy_for_site",
                side_effect=WDKError("WDK error"),
            ),
        ):
            result = await agent.do_function_call(call, "tc1")

        parsed = json.loads(result.message.text)
        assert parsed["ok"] is True
        assert parsed["stepId"] == "s1"

    async def test_parse_jsonish_succeeds_on_auto_sync_result(self, agent):
        """parse_jsonish must succeed on the auto-build merged result.

        This is the exact function that streaming.py uses to parse tool results.
        If this fails, no strategy events are emitted to the frontend.
        """
        call = FunctionCall(name="create_step", arguments="{}")

        with (
            patch("kani.Kani.do_function_call", return_value=_parent_result()),
            patch(
                "veupath_chatbot.ai.agents.executor.sync_strategy_for_site",
                return_value=_sync_result(),
            ),
            patch(
                "veupath_chatbot.ai.agents.executor.GeneSetService",
                side_effect=ImportError("skip"),
            ),
        ):
            result = await agent.do_function_call(call, "tc1")

        parsed = parse_jsonish(result.message.text)
        assert parsed is not None
        assert isinstance(parsed, dict)
        assert "stepId" in parsed
        assert "autoBuild" in parsed


# ---------------------------------------------------------------------------
# Tests: event emission after auto-build
# ---------------------------------------------------------------------------


class TestAutoBuildEventEmission:
    """Auto-build must emit both strategy_link and graph_snapshot events."""

    @pytest.fixture
    def agent(self) -> PathfinderAgent:
        agent = _make_agent()
        graph = agent.strategy_session.get_graph(None)
        assert graph is not None
        step = _step("s1")
        graph.add_step(step)
        graph.record_type = "gene"
        return agent

    async def test_emits_strategy_link_event(self, agent):
        """Auto-build must emit a strategy_link event with wdkStrategyId."""
        call = FunctionCall(name="create_step", arguments="{}")

        with (
            patch("kani.Kani.do_function_call", return_value=_parent_result()),
            patch(
                "veupath_chatbot.ai.agents.executor.sync_strategy_for_site",
                return_value=_sync_result(),
            ),
            patch(
                "veupath_chatbot.ai.agents.executor.GeneSetService",
                side_effect=ImportError("skip"),
            ),
        ):
            await agent.do_function_call(call, "tc1")

        events = _drain_queue(agent.event_queue)
        link_events = [e for e in events if e.get("type") == "strategy_link"]
        assert len(link_events) == 1
        assert link_events[0]["data"]["wdkStrategyId"] == 999

    async def test_emits_graph_snapshot_after_build(self, agent):
        """Auto-build must emit a graph_snapshot with updated WDK IDs/counts."""
        call = FunctionCall(name="create_step", arguments="{}")

        with (
            patch("kani.Kani.do_function_call", return_value=_parent_result()),
            patch(
                "veupath_chatbot.ai.agents.executor.sync_strategy_for_site",
                return_value=_sync_result(),
            ),
            patch(
                "veupath_chatbot.ai.agents.executor.GeneSetService",
                side_effect=ImportError("skip"),
            ),
        ):
            await agent.do_function_call(call, "tc1")

        events = _drain_queue(agent.event_queue)
        snapshot_events = [e for e in events if e.get("type") == "graph_snapshot"]
        assert len(snapshot_events) >= 1, (
            "Auto-build must emit a graph_snapshot so the frontend gets WDK step IDs and counts"
        )

    async def test_graph_snapshot_comes_after_strategy_link(self, agent):
        """graph_snapshot must be emitted AFTER strategy_link (ordering matters)."""
        call = FunctionCall(name="create_step", arguments="{}")

        with (
            patch("kani.Kani.do_function_call", return_value=_parent_result()),
            patch(
                "veupath_chatbot.ai.agents.executor.sync_strategy_for_site",
                return_value=_sync_result(),
            ),
            patch(
                "veupath_chatbot.ai.agents.executor.GeneSetService",
                side_effect=ImportError("skip"),
            ),
        ):
            await agent.do_function_call(call, "tc1")

        events = _drain_queue(agent.event_queue)
        types = [e["type"] for e in events]
        link_idx = types.index("strategy_link")
        snapshot_idx = types.index("graph_snapshot")
        assert snapshot_idx > link_idx

    async def test_no_events_emitted_on_build_failure(self, agent):
        """When auto-build fails, no strategy_link or graph_snapshot is emitted."""
        call = FunctionCall(name="create_step", arguments="{}")

        with (
            patch("kani.Kani.do_function_call", return_value=_parent_result()),
            patch(
                "veupath_chatbot.ai.agents.executor.sync_strategy_for_site",
                side_effect=WDKError("WDK down"),
            ),
        ):
            await agent.do_function_call(call, "tc1")

        events = _drain_queue(agent.event_queue)
        link_events = [e for e in events if e.get("type") == "strategy_link"]
        assert len(link_events) == 0


# ---------------------------------------------------------------------------
# Tests: auto-build gating conditions
# ---------------------------------------------------------------------------


class TestAutoBuildGating:
    """Auto-build should only fire under specific conditions."""

    async def test_no_auto_build_for_non_graph_tools(self):
        """Non-graph-mutating tools should not trigger auto-build."""
        agent = _make_agent()
        graph = agent.strategy_session.get_graph(None)
        assert graph is not None
        step = _step("s1")
        graph.add_step(step)
        graph.record_type = "gene"

        call = FunctionCall(name="search_for_searches", arguments="{}")

        with patch("kani.Kani.do_function_call", return_value=_parent_result()):
            result = await agent.do_function_call(call, "tc1")

        # Should be unchanged — no autoBuild key
        parsed = json.loads(result.message.text)
        assert "autoBuild" not in parsed

    async def test_multiple_roots_skips_build_with_diagnostic(self):
        """With multiple roots, auto-build is skipped but result includes diagnostic info."""
        agent = _make_agent()
        graph = agent.strategy_session.get_graph(None)
        assert graph is not None
        graph.add_step(_step("s1"))
        graph.add_step(
            PlanStepNode(
                search_name="GenesByLocation",
                parameters={},
                id="s2",
            )
        )
        graph.record_type = "gene"
        assert len(graph.roots) == 2

        call = FunctionCall(name="create_step", arguments="{}")

        with patch("kani.Kani.do_function_call", return_value=_parent_result()):
            result = await agent.do_function_call(call, "tc1")

        parsed = json.loads(result.message.text)
        assert "autoBuild" in parsed, (
            "Model must be told WHY auto-build was skipped — otherwise it has no WDK IDs"
        )
        assert parsed["autoBuild"]["ok"] is False
        assert parsed["autoBuild"]["skipped"] is True
        assert parsed["autoBuild"]["reason"] == "multiple_roots"
        assert parsed["autoBuild"]["rootCount"] == 2

    async def test_rebuild_after_mutation_with_single_root(self):
        """When previously built graph is mutated back to 1 root, auto-build re-fires."""
        agent = _make_agent()
        graph = agent.strategy_session.get_graph(None)
        assert graph is not None
        graph.add_step(_step("s1"))
        graph.record_type = "gene"
        graph.wdk_strategy_id = 123  # Previously built
        graph.wdk_step_ids = {"s1": 100}
        graph.step_counts = {"s1": 42}

        call = FunctionCall(name="create_step", arguments="{}")

        with (
            patch("kani.Kani.do_function_call", return_value=_parent_result()),
            patch(
                "veupath_chatbot.ai.agents.executor.sync_strategy_for_site",
                return_value=_sync_result(wdk_strategy_id=456),
            ),
            patch(
                "veupath_chatbot.ai.agents.executor.GeneSetService",
                side_effect=ImportError("skip"),
            ),
        ):
            result = await agent.do_function_call(call, "tc1")

        parsed = json.loads(result.message.text)
        assert "autoBuild" in parsed, (
            "Auto-build must re-fire after mutation even if previously built"
        )
        assert parsed["autoBuild"]["ok"] is True
        assert parsed["autoBuild"]["wdkStrategyId"] == 456

    async def test_already_built_multiple_roots_includes_existing_wdk_info(self):
        """When previously built and now multiple roots, result includes existing WDK mapping."""
        agent = _make_agent()
        graph = agent.strategy_session.get_graph(None)
        assert graph is not None
        graph.add_step(_step("s1"))
        graph.add_step(
            PlanStepNode(
                search_name="GenesByLocation",
                parameters={},
                id="s2",
            )
        )
        graph.record_type = "gene"
        graph.wdk_strategy_id = 123
        graph.wdk_step_ids = {"s1": 100}
        graph.step_counts = {"s1": 42}
        assert len(graph.roots) == 2

        call = FunctionCall(name="delegate_strategy_subtasks", arguments="{}")

        with patch("kani.Kani.do_function_call", return_value=_parent_result()):
            result = await agent.do_function_call(call, "tc1")

        parsed = json.loads(result.message.text)
        assert "autoBuild" in parsed
        assert parsed["autoBuild"]["ok"] is False
        assert parsed["autoBuild"]["skipped"] is True
        # Must include existing WDK mappings so model can use them
        assert parsed["autoBuild"]["existingWdkStepIds"] == {"s1": 100}

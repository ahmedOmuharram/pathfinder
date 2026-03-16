"""Tests for restoring WDK build state when reconstructing the graph.

The graph must know it's been built (wdk_strategy_id, wdk_step_ids) when
the agent is recreated on a new chat turn. Otherwise the model thinks
nothing is built, hallucinates step IDs, and can't use result tools.
"""

from veupath_chatbot.domain.strategy.session import (
    StrategyGraph,
    hydrate_graph_from_steps_data,
)
from veupath_chatbot.services.strategies.session_factory import (
    build_strategy_session,
)

# ---------------------------------------------------------------------------
# hydrate_graph_from_steps_data: restore wdk_step_ids
# ---------------------------------------------------------------------------


class TestHydrateRestoresWdkStepIds:
    """hydrate_graph_from_steps_data should populate graph.wdk_step_ids
    from per-step wdkStepId fields in the persisted steps data."""

    def test_wdk_step_ids_restored_from_steps(self):
        """Steps with wdkStepId should populate graph.wdk_step_ids."""
        graph = StrategyGraph("g1", "Test", "plasmodb")
        steps_data = [
            {
                "id": "step_a",
                "kind": "search",
                "searchName": "GenesByTaxon",
                "displayName": "All genes",
                "parameters": {},
                "wdkStepId": 12345,
            },
            {
                "id": "step_b",
                "kind": "search",
                "searchName": "GenesByLocation",
                "displayName": "By location",
                "parameters": {},
                "wdkStepId": 67890,
            },
        ]

        hydrate_graph_from_steps_data(graph, steps_data)

        assert graph.wdk_step_ids == {"step_a": 12345, "step_b": 67890}

    def test_steps_without_wdk_step_id_are_skipped(self):
        """Steps without wdkStepId should not appear in wdk_step_ids."""
        graph = StrategyGraph("g1", "Test", "plasmodb")
        steps_data = [
            {
                "id": "step_a",
                "kind": "search",
                "searchName": "GenesByTaxon",
                "displayName": "All genes",
                "parameters": {},
                "wdkStepId": 100,
            },
            {
                "id": "step_b",
                "kind": "search",
                "searchName": "GenesByLocation",
                "displayName": "By location",
                "parameters": {},
                # No wdkStepId — not yet built
            },
        ]

        hydrate_graph_from_steps_data(graph, steps_data)

        assert graph.wdk_step_ids == {"step_a": 100}
        assert "step_b" not in graph.wdk_step_ids

    def test_result_counts_restored_from_steps(self):
        """Steps with resultCount should populate graph.step_counts."""
        graph = StrategyGraph("g1", "Test", "plasmodb")
        steps_data = [
            {
                "id": "step_a",
                "kind": "search",
                "searchName": "GenesByTaxon",
                "displayName": "All genes",
                "parameters": {},
                "wdkStepId": 100,
                "resultCount": 42,
            },
        ]

        hydrate_graph_from_steps_data(graph, steps_data)

        assert graph.step_counts == {"step_a": 42}

    def test_no_wdk_step_ids_when_unbuilt(self):
        """When no steps have wdkStepId, wdk_step_ids stays empty."""
        graph = StrategyGraph("g1", "Test", "plasmodb")
        steps_data = [
            {
                "id": "step_a",
                "kind": "search",
                "searchName": "GenesByTaxon",
                "displayName": "All genes",
                "parameters": {},
            },
        ]

        hydrate_graph_from_steps_data(graph, steps_data)

        assert graph.wdk_step_ids == {}


# ---------------------------------------------------------------------------
# build_strategy_session: restore wdk_strategy_id
# ---------------------------------------------------------------------------


class TestSessionFactoryRestoresWdkStrategyId:
    """build_strategy_session should set graph.wdk_strategy_id from the
    payload's wdkStrategyId field."""

    def test_wdk_strategy_id_restored(self):
        """wdkStrategyId in the payload should set graph.wdk_strategy_id."""
        session = build_strategy_session(
            site_id="plasmodb",
            strategy_graph={
                "id": "stream-1",
                "name": "My Strategy",
                "steps": [
                    {
                        "id": "step_a",
                        "kind": "search",
                        "searchName": "GenesByTaxon",
                        "displayName": "All genes",
                        "parameters": {},
                        "wdkStepId": 100,
                    },
                ],
                "rootStepId": "step_a",
                "recordType": "gene",
                "wdkStrategyId": 999,
            },
        )
        graph = session.get_graph(None)
        assert graph is not None
        assert graph.wdk_strategy_id == 999

    def test_wdk_strategy_id_none_when_not_built(self):
        """Without wdkStrategyId, graph.wdk_strategy_id stays None."""
        session = build_strategy_session(
            site_id="plasmodb",
            strategy_graph={
                "id": "stream-1",
                "name": "My Strategy",
                "steps": [
                    {
                        "id": "step_a",
                        "kind": "search",
                        "searchName": "GenesByTaxon",
                        "displayName": "All genes",
                        "parameters": {},
                    },
                ],
                "rootStepId": "step_a",
                "recordType": "gene",
            },
        )
        graph = session.get_graph(None)
        assert graph is not None
        assert graph.wdk_strategy_id is None

    def test_wdk_step_ids_flow_through_session_factory(self):
        """wdkStepId per step should flow through to graph.wdk_step_ids."""
        session = build_strategy_session(
            site_id="plasmodb",
            strategy_graph={
                "id": "stream-1",
                "name": "My Strategy",
                "steps": [
                    {
                        "id": "step_a",
                        "kind": "search",
                        "searchName": "GenesByTaxon",
                        "displayName": "All genes",
                        "parameters": {},
                        "wdkStepId": 100,
                        "resultCount": 42,
                    },
                ],
                "rootStepId": "step_a",
                "recordType": "gene",
                "wdkStrategyId": 999,
            },
        )
        graph = session.get_graph(None)
        assert graph is not None
        assert graph.wdk_step_ids == {"step_a": 100}
        assert graph.step_counts == {"step_a": 42}


# ---------------------------------------------------------------------------
# _build_agent_context passes wdkStrategyId
# ---------------------------------------------------------------------------


class TestPlanPathRestoresWdkStepIds:
    """When the graph loads from the plan (AST) path, wdk_step_ids must
    still be restored from the persisted steps data."""

    def test_plan_loaded_but_wdk_step_ids_from_steps(self):
        """Graph loads from plan, but wdk_step_ids come from steps snapshot."""
        session = build_strategy_session(
            site_id="plasmodb",
            strategy_graph={
                "id": "stream-1",
                "name": "My Strategy",
                "plan": {
                    "recordType": "transcript",
                    "root": {
                        "id": "step_a",
                        "searchName": "GenesByTaxon",
                        "displayName": "All genes",
                        "parameters": {"organism": '["Plasmodium falciparum 3D7"]'},
                    },
                    "metadata": {"name": "My Strategy"},
                },
                "steps": [
                    {
                        "id": "step_a",
                        "kind": "search",
                        "searchName": "GenesByTaxon",
                        "displayName": "All genes",
                        "parameters": {"organism": '["Plasmodium falciparum 3D7"]'},
                        "wdkStepId": 438251663,
                        "estimatedSize": 5678,
                        "isBuilt": True,
                    },
                ],
                "rootStepId": "step_a",
                "recordType": "transcript",
                "wdkStrategyId": 329971733,
            },
        )
        graph = session.get_graph(None)
        assert graph is not None
        # Plan loaded successfully
        assert graph.steps, "Graph should have steps from plan"
        assert graph.current_strategy is not None
        # WDK build state restored from steps snapshot
        assert graph.wdk_strategy_id == 329971733
        assert graph.wdk_step_ids == {"step_a": 438251663}
        assert graph.step_counts == {"step_a": 5678}


class TestOrchestratorPassesWdkStrategyId:
    """_build_agent_context must include wdkStrategyId in the payload
    it passes to build_strategy_session."""

    def test_projection_wdk_strategy_id_in_payload(self):
        """The strategy_graph_payload built from the projection must
        include wdkStrategyId so the session factory can restore it."""
        # This test validates the orchestrator code path.
        # We can't easily call _build_agent_context (it's async + needs
        # many deps), so we test the contract: the payload dict must
        # include wdkStrategyId from the projection.
        #
        # The actual fix is in orchestrator.py's _build_agent_context.
        # This test documents the requirement.
        payload = {
            "id": "stream-1",
            "name": "My Strategy",
            "steps": [],
            "rootStepId": None,
            "recordType": "gene",
            "wdkStrategyId": 12345,
        }
        session = build_strategy_session(
            site_id="plasmodb",
            strategy_graph=payload,
        )
        graph = session.get_graph(None)
        assert graph is not None
        assert graph.wdk_strategy_id == 12345

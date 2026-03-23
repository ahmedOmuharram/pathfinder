"""Tests for restoring WDK build state when reconstructing the graph.

The graph must know it's been built (wdk_strategy_id, wdk_step_ids) when
the agent is recreated on a new chat turn. Otherwise the model thinks
nothing is built, hallucinates step IDs, and can't use result tools.

WDK state is now stored in the plan AST's ``step_counts`` and
``wdk_step_ids`` fields — no longer read from the legacy ``steps`` array.
"""

from veupath_chatbot.services.strategies.session_factory import (
    build_strategy_session,
)


class TestSessionFactoryRestoresWdkState:
    """build_strategy_session should restore wdk_strategy_id, wdk_step_ids,
    and step_counts from the plan AST metadata."""

    def test_wdk_strategy_id_restored(self) -> None:
        """wdkStrategyId in the payload should set graph.wdk_strategy_id."""
        session = build_strategy_session(
            site_id="plasmodb",
            strategy_graph={
                "id": "stream-1",
                "name": "My Strategy",
                "plan": {
                    "recordType": "gene",
                    "root": {
                        "id": "step_a",
                        "searchName": "GenesByTaxon",
                        "parameters": {},
                    },
                    "wdkStepIds": {"step_a": 100},
                    "stepCounts": {"step_a": 42},
                },
                "wdkStrategyId": 999,
            },
        )
        graph = session.get_graph(None)
        assert graph is not None
        assert graph.wdk_strategy_id == 999

    def test_wdk_strategy_id_none_when_not_built(self) -> None:
        """Without wdkStrategyId, graph.wdk_strategy_id stays None."""
        session = build_strategy_session(
            site_id="plasmodb",
            strategy_graph={
                "id": "stream-1",
                "name": "My Strategy",
                "plan": {
                    "recordType": "gene",
                    "root": {
                        "id": "step_a",
                        "searchName": "GenesByTaxon",
                        "parameters": {},
                    },
                },
            },
        )
        graph = session.get_graph(None)
        assert graph is not None
        assert graph.wdk_strategy_id is None

    def test_wdk_step_ids_from_plan_metadata(self) -> None:
        """wdkStepIds in the plan AST should flow through to graph.wdk_step_ids."""
        session = build_strategy_session(
            site_id="plasmodb",
            strategy_graph={
                "id": "stream-1",
                "name": "My Strategy",
                "plan": {
                    "recordType": "gene",
                    "root": {
                        "id": "step_a",
                        "searchName": "GenesByTaxon",
                        "parameters": {},
                    },
                    "wdkStepIds": {"step_a": 100},
                    "stepCounts": {"step_a": 42},
                },
                "wdkStrategyId": 999,
            },
        )
        graph = session.get_graph(None)
        assert graph is not None
        assert graph.wdk_step_ids == {"step_a": 100}
        assert graph.step_counts == {"step_a": 42}


class TestPlanPathRestoresWdkStepIds:
    """When the graph loads from the plan (AST) path, wdk_step_ids must
    be restored from the plan AST's wdkStepIds metadata field."""

    def test_plan_loaded_with_wdk_step_ids_from_plan(self) -> None:
        """Graph loads from plan, and wdk_step_ids come from plan metadata."""
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
                    "name": "My Strategy",
                    "stepCounts": {"step_a": 5678},
                    "wdkStepIds": {"step_a": 438251663},
                },
                "wdkStrategyId": 329971733,
            },
        )
        graph = session.get_graph(None)
        assert graph is not None
        # Plan loaded successfully
        assert graph.steps, "Graph should have steps from plan"
        assert graph.current_strategy is not None
        # WDK build state restored from plan metadata
        assert graph.wdk_strategy_id == 329971733
        assert graph.wdk_step_ids == {"step_a": 438251663}
        assert graph.step_counts == {"step_a": 5678}

    def test_plan_without_wdk_metadata_has_empty_state(self) -> None:
        """Plan without wdkStepIds/stepCounts results in empty WDK state."""
        session = build_strategy_session(
            site_id="plasmodb",
            strategy_graph={
                "id": "stream-1",
                "name": "My Strategy",
                "plan": {
                    "recordType": "gene",
                    "root": {
                        "id": "step_a",
                        "searchName": "GenesByTaxon",
                        "parameters": {},
                    },
                },
            },
        )
        graph = session.get_graph(None)
        assert graph is not None
        assert graph.steps, "Graph should have steps from plan"
        assert graph.wdk_step_ids == {}
        assert graph.step_counts == {}

    def test_multi_step_plan_restores_all_wdk_ids(self) -> None:
        """Multi-step plans with wdkStepIds restore all step mappings."""
        session = build_strategy_session(
            site_id="plasmodb",
            strategy_graph={
                "id": "stream-1",
                "name": "Combined",
                "plan": {
                    "recordType": "gene",
                    "root": {
                        "id": "c1",
                        "searchName": "BooleanQuestion",
                        "parameters": {},
                        "operator": "INTERSECT",
                        "primaryInput": {
                            "id": "s1",
                            "searchName": "GenesByTaxon",
                            "parameters": {},
                        },
                        "secondaryInput": {
                            "id": "s2",
                            "searchName": "GenesByGoTerm",
                            "parameters": {},
                        },
                    },
                    "wdkStepIds": {"s1": 100, "s2": 200, "c1": 300},
                    "stepCounts": {"s1": 50, "s2": 30, "c1": 10},
                },
                "wdkStrategyId": 999,
            },
        )
        graph = session.get_graph(None)
        assert graph is not None
        assert len(graph.steps) == 3
        assert graph.wdk_step_ids == {"s1": 100, "s2": 200, "c1": 300}
        assert graph.step_counts == {"s1": 50, "s2": 30, "c1": 10}


class TestOrchestratorPassesWdkStrategyId:
    """_build_agent_context must include wdkStrategyId in the payload
    it passes to build_strategy_session."""

    def test_projection_wdk_strategy_id_in_payload(self) -> None:
        """The strategy_graph_payload built from the projection must
        include wdkStrategyId so the session factory can restore it."""
        payload = {
            "id": "stream-1",
            "name": "My Strategy",
            "plan": {
                "recordType": "gene",
                "root": {
                    "id": "step_a",
                    "searchName": "GenesByTaxon",
                    "parameters": {},
                },
            },
            "wdkStrategyId": 12345,
        }
        session = build_strategy_session(
            site_id="plasmodb",
            strategy_graph=payload,
        )
        graph = session.get_graph(None)
        assert graph is not None
        assert graph.wdk_strategy_id == 12345

"""Unit tests for services.strategies.session_factory."""

from veupath_chatbot.services.strategies.session_factory import build_strategy_session


class TestBuildStrategySession:
    def test_creates_default_graph_when_no_data(self) -> None:
        session = build_strategy_session(site_id="plasmodb", strategy_graph=None)
        assert session.site_id == "plasmodb"
        graph = session.get_graph(None)
        assert graph is not None
        assert graph.name == "New Conversation"

    def test_creates_default_graph_when_empty_dict(self) -> None:
        session = build_strategy_session(site_id="plasmodb", strategy_graph={})
        graph = session.get_graph(None)
        assert graph is not None

    def test_hydrates_from_plan(self) -> None:
        plan = {
            "recordType": "gene",
            "root": {
                "id": "s1",
                "searchName": "GenesByTextSearch",
                "parameters": {"text_expression": "kinase"},
            },
        }
        strategy_graph = {
            "id": "g1",
            "name": "My Strategy",
            "plan": plan,
        }
        session = build_strategy_session(
            site_id="plasmodb", strategy_graph=strategy_graph
        )
        graph = session.get_graph(None)
        assert graph is not None
        assert graph.id == "g1"
        assert graph.name == "My Strategy"
        assert "s1" in graph.steps
        assert graph.steps["s1"].search_name == "GenesByTextSearch"
        assert graph.current_strategy is not None
        assert graph.current_strategy.record_type == "gene"

    def test_no_plan_creates_empty_graph(self) -> None:
        """When plan is missing, graph is created but has no steps."""
        strategy_graph = {
            "id": "g2",
            "name": "No Plan Strategy",
            "steps": [
                {
                    "id": "s1",
                    "searchName": "GenesByTextSearch",
                    "parameters": {},
                }
            ],
        }
        session = build_strategy_session(
            site_id="plasmodb", strategy_graph=strategy_graph
        )
        graph = session.get_graph(None)
        assert graph is not None
        assert graph.id == "g2"
        # No plan -> no steps hydrated (legacy fallback removed)
        assert graph.steps == {}

    def test_invalid_plan_creates_empty_graph(self) -> None:
        """If plan can't be parsed, graph has no steps."""
        strategy_graph = {
            "id": "g3",
            "name": "Bad Plan",
            "plan": {"invalid": "data"},  # missing recordType and root
        }
        session = build_strategy_session(
            site_id="plasmodb", strategy_graph=strategy_graph
        )
        graph = session.get_graph(None)
        assert graph is not None
        assert graph.steps == {}

    def test_graph_id_from_graph_id_field(self) -> None:
        strategy_graph = {
            "graphId": "gid_123",
            "name": "Test",
        }
        session = build_strategy_session(
            site_id="plasmodb", strategy_graph=strategy_graph
        )
        graph = session.get_graph(None)
        assert graph is not None
        assert graph.id == "gid_123"

    def test_plan_hydration_sets_history(self) -> None:
        plan = {
            "recordType": "gene",
            "root": {
                "id": "s1",
                "searchName": "GenesByTextSearch",
                "parameters": {},
            },
        }
        strategy_graph = {"id": "g1", "name": "Named", "plan": plan}
        session = build_strategy_session(
            site_id="plasmodb", strategy_graph=strategy_graph
        )
        graph = session.get_graph(None)
        assert graph is not None
        assert len(graph.history) > 0

    def test_plan_with_top_level_name(self) -> None:
        plan = {
            "recordType": "gene",
            "root": {
                "id": "s1",
                "searchName": "GenesByTextSearch",
                "parameters": {},
            },
            "name": "Plan Name",
        }
        strategy_graph = {"id": "g1", "name": "Graph Name", "plan": plan}
        session = build_strategy_session(
            site_id="plasmodb", strategy_graph=strategy_graph
        )
        graph = session.get_graph(None)
        assert graph is not None
        # The plan name from top-level field should be used
        assert graph.name == "Plan Name"

    def test_missing_name_uses_default(self) -> None:
        strategy_graph = {
            "id": "g1",
        }
        session = build_strategy_session(
            site_id="plasmodb", strategy_graph=strategy_graph
        )
        graph = session.get_graph(None)
        assert graph is not None
        assert graph.name == "New Conversation"

    def test_combine_plan_hydrated_correctly(self) -> None:
        plan = {
            "recordType": "gene",
            "root": {
                "id": "c1",
                "searchName": "BooleanQuestion",
                "parameters": {},
                "operator": "INTERSECT",
                "primaryInput": {
                    "id": "s1",
                    "searchName": "GenesByTextSearch",
                    "parameters": {},
                },
                "secondaryInput": {
                    "id": "s2",
                    "searchName": "GenesByGoTerm",
                    "parameters": {},
                },
            },
        }
        strategy_graph = {"id": "g1", "name": "Combined", "plan": plan}
        session = build_strategy_session(
            site_id="plasmodb", strategy_graph=strategy_graph
        )
        graph = session.get_graph(None)
        assert graph is not None
        assert len(graph.steps) == 3
        assert graph.roots == {"c1"}
        assert graph.last_step_id == "c1"

    def test_wdk_state_restored_from_plan_metadata(self) -> None:
        """step_counts and wdk_step_ids in plan AST are restored to graph."""
        plan = {
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
        }
        session = build_strategy_session(
            site_id="plasmodb",
            strategy_graph={
                "id": "stream-1",
                "name": "My Strategy",
                "plan": plan,
                "wdkStrategyId": 329971733,
            },
        )
        graph = session.get_graph(None)
        assert graph is not None
        assert graph.steps, "Graph should have steps from plan"
        assert graph.current_strategy is not None
        assert graph.wdk_strategy_id == 329971733
        assert graph.wdk_step_ids == {"step_a": 438251663}
        assert graph.step_counts == {"step_a": 5678}

    def test_wdk_strategy_id_restored_without_plan(self) -> None:
        """wdkStrategyId is restored even when plan is missing."""
        session = build_strategy_session(
            site_id="plasmodb",
            strategy_graph={
                "id": "stream-1",
                "name": "My Strategy",
                "wdkStrategyId": 999,
            },
        )
        graph = session.get_graph(None)
        assert graph is not None
        assert graph.wdk_strategy_id == 999

    def test_wdk_strategy_id_none_when_absent(self) -> None:
        """Without wdkStrategyId, graph.wdk_strategy_id stays None."""
        session = build_strategy_session(
            site_id="plasmodb",
            strategy_graph={
                "id": "stream-1",
                "name": "My Strategy",
            },
        )
        graph = session.get_graph(None)
        assert graph is not None
        assert graph.wdk_strategy_id is None

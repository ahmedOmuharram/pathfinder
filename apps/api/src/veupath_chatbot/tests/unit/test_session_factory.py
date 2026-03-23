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

    def test_hydrates_from_steps_data_fallback(self) -> None:
        """When plan is missing, falls back to steps + rootStepId."""
        strategy_graph = {
            "id": "g2",
            "name": "Fallback Strategy",
            "rootStepId": "s1",
            "recordType": "gene",
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
        assert "s1" in graph.steps
        assert graph.last_step_id == "s1"
        assert graph.record_type == "gene"

    def test_invalid_plan_falls_back_to_steps(self) -> None:
        """If plan can't be parsed, falls back to steps data."""
        strategy_graph = {
            "id": "g3",
            "name": "Bad Plan",
            "plan": {"invalid": "data"},  # missing recordType and root
            "steps": [
                {"id": "s1", "searchName": "GenesByTextSearch"},
            ],
        }
        session = build_strategy_session(
            site_id="plasmodb", strategy_graph=strategy_graph
        )
        graph = session.get_graph(None)
        assert graph is not None
        assert "s1" in graph.steps

    def test_graph_id_from_graph_id_field(self) -> None:
        strategy_graph = {
            "graphId": "gid_123",
            "name": "Test",
            "steps": [{"id": "s1", "searchName": "S1"}],
        }
        session = build_strategy_session(
            site_id="plasmodb", strategy_graph=strategy_graph
        )
        graph = session.get_graph(None)
        assert graph is not None
        assert graph.id == "gid_123"

    def test_record_type_from_alternative_key(self) -> None:
        strategy_graph = {
            "id": "g1",
            "name": "Test",
            "record_type": "transcript",
            "steps": [{"id": "s1", "searchName": "S1"}],
        }
        session = build_strategy_session(
            site_id="plasmodb", strategy_graph=strategy_graph
        )
        graph = session.get_graph(None)
        assert graph is not None
        assert graph.record_type == "transcript"

    def test_root_step_id_from_alternative_key(self) -> None:
        strategy_graph = {
            "id": "g1",
            "name": "Test",
            "root_step_id": "s1",
            "steps": [{"id": "s1", "searchName": "S1"}],
        }
        session = build_strategy_session(
            site_id="plasmodb", strategy_graph=strategy_graph
        )
        graph = session.get_graph(None)
        assert graph is not None
        assert graph.last_step_id == "s1"

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
            "steps": [{"id": "s1", "searchName": "S1"}],
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

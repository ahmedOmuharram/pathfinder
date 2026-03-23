"""Unit tests for services.chat.events — tool_result_to_events."""

from veupath_chatbot.services.chat.events import (
    EventType,
    tool_result_to_events,
)


class TestToolResultToEventsBasics:
    def test_non_dict_returns_empty(self):
        assert tool_result_to_events("not a dict") == []
        assert tool_result_to_events(42) == []
        assert tool_result_to_events([1, 2]) == []

    def test_empty_dict_returns_empty(self):
        assert tool_result_to_events({}) == []


class TestCitationsEvent:
    def test_citations_list_emitted(self):
        result = {"citations": [{"url": "http://example.com", "title": "Example"}]}
        events = tool_result_to_events(result)
        assert len(events) == 1
        assert events[0]["type"] == EventType.CITATIONS
        assert events[0]["data"]["citations"] == result["citations"]

    def test_empty_citations_list_not_emitted(self):
        result = {"citations": []}
        events = tool_result_to_events(result)
        assert len(events) == 0

    def test_non_list_citations_not_emitted(self):
        result = {"citations": "not a list"}
        events = tool_result_to_events(result)
        assert len(events) == 0

    def test_none_citations_not_emitted(self):
        result = {"citations": None}
        events = tool_result_to_events(result)
        assert len(events) == 0


class TestPlanningArtifactEvent:
    def test_truthy_planning_artifact_emitted(self):
        artifact = {"id": "art1", "title": "Test"}
        result = {"planningArtifact": artifact}
        events = tool_result_to_events(result)
        assert len(events) == 1
        assert events[0]["type"] == EventType.PLANNING_ARTIFACT
        assert events[0]["data"]["planningArtifact"] == artifact

    def test_falsy_planning_artifact_not_emitted(self):
        for val in [None, "", 0, False, {}, []]:
            result = {"planningArtifact": val}
            events = tool_result_to_events(result)
            artifact_events = [e for e in events if e["type"] == EventType.PLANNING_ARTIFACT]
            assert len(artifact_events) == 0, f"Should not emit for {val!r}"


class TestReasoningEvent:
    def test_reasoning_string_emitted(self):
        result = {"reasoning": "The user wants kinases."}
        events = tool_result_to_events(result)
        assert len(events) == 1
        assert events[0]["type"] == EventType.REASONING
        assert events[0]["data"]["reasoning"] == "The user wants kinases."

    def test_whitespace_only_reasoning_not_emitted(self):
        result = {"reasoning": "   "}
        events = tool_result_to_events(result)
        assert len(events) == 0

    def test_empty_reasoning_not_emitted(self):
        result = {"reasoning": ""}
        events = tool_result_to_events(result)
        assert len(events) == 0

    def test_non_string_reasoning_not_emitted(self):
        result = {"reasoning": 42}
        events = tool_result_to_events(result)
        assert len(events) == 0


class TestConversationTitleEvent:
    def test_conversation_title_emits_strategy_meta(self):
        result = {"conversationTitle": "My Strategy"}
        events = tool_result_to_events(result)
        assert len(events) == 1
        assert events[0]["type"] == EventType.STRATEGY_META
        assert events[0]["data"]["name"] == "My Strategy"

    def test_conversation_title_stripped(self):
        result = {"conversationTitle": "  Trimmed Title  "}
        events = tool_result_to_events(result)
        assert events[0]["data"]["name"] == "Trimmed Title"

    def test_whitespace_only_title_not_emitted(self):
        result = {"conversationTitle": "   "}
        events = tool_result_to_events(result)
        assert len(events) == 0

    def test_non_string_title_not_emitted(self):
        result = {"conversationTitle": 123}
        events = tool_result_to_events(result)
        assert len(events) == 0


class TestExecutorBuildRequestEvent:
    def test_dict_executor_build_request_emitted(self):
        req = {"steps": ["a", "b"]}
        result = {"executorBuildRequest": req}
        events = tool_result_to_events(result)
        assert len(events) == 1
        assert events[0]["type"] == EventType.EXECUTOR_BUILD_REQUEST
        assert events[0]["data"]["executorBuildRequest"] == req

    def test_non_dict_executor_build_request_not_emitted(self):
        result = {"executorBuildRequest": "not a dict"}
        events = tool_result_to_events(result)
        ebr_events = [e for e in events if e["type"] == EventType.EXECUTOR_BUILD_REQUEST]
        assert len(ebr_events) == 0


class TestStrategyUpdateEvent:
    def test_step_id_without_get_graph(self):
        result = {"stepId": "s1", "graphId": "g1", "displayName": "Step 1"}
        events = tool_result_to_events(result)
        # stepId triggers strategy_update; graphId+name triggers strategy_meta
        update_events = [e for e in events if e["type"] == EventType.STRATEGY_UPDATE]
        assert len(update_events) == 1
        data = update_events[0]["data"]
        assert data["graphId"] == "g1"
        assert data["step"] == result
        assert data["allSteps"] == []

    def test_step_id_with_get_graph_returning_none(self):
        result = {"stepId": "s1", "graphId": "g1"}
        events = tool_result_to_events(result, get_graph=lambda gid: None)
        update_events = [e for e in events if e["type"] == EventType.STRATEGY_UPDATE]
        assert len(update_events) == 1
        assert update_events[0]["data"]["allSteps"] == []

    def test_step_id_with_get_graph_returning_graph(self):
        # Create a minimal mock graph with steps
        class MockStep:
            def __init__(self, display_name, kind):
                self.display_name = display_name
                self._kind = kind

            def infer_kind(self):
                return self._kind

        class MockGraph:
            def __init__(self):
                self.steps = {
                    "s1": MockStep("Search", "search"),
                    "s2": MockStep("Combine", "combine"),
                }

        graph = MockGraph()
        result = {"stepId": "s1", "graphId": "g1"}
        events = tool_result_to_events(result, get_graph=lambda gid: graph)
        update_events = [e for e in events if e["type"] == EventType.STRATEGY_UPDATE]
        assert len(update_events) == 1
        all_steps = update_events[0]["data"]["allSteps"]
        assert len(all_steps) == 2
        step_ids = {s["id"] for s in all_steps}
        assert step_ids == {"s1", "s2"}

    def test_non_string_graph_id_coerced_to_none(self):
        result = {"stepId": "s1", "graphId": 999}
        events = tool_result_to_events(result)
        update_events = [e for e in events if e["type"] == EventType.STRATEGY_UPDATE]
        # Non-string graphId is coerced to None and excluded by exclude_none
        assert "graphId" not in update_events[0]["data"]


class TestGraphSnapshotEvent:
    def test_graph_snapshot_emitted(self):
        snapshot = {"steps": [], "graphId": "g1"}
        result = {"graphSnapshot": snapshot}
        events = tool_result_to_events(result)
        snap_events = [e for e in events if e["type"] == EventType.GRAPH_SNAPSHOT]
        assert len(snap_events) == 1
        assert snap_events[0]["data"]["graphSnapshot"] == snapshot
        assert snap_events[0]["data"]["graphSnapshot"]["graphId"] == "g1"

    def test_graph_snapshot_uses_result_graph_id_as_fallback(self):
        snapshot = {"steps": []}  # No graphId in snapshot
        result = {"graphSnapshot": snapshot, "graphId": "g_fallback"}
        events = tool_result_to_events(result)
        snap_events = [e for e in events if e["type"] == EventType.GRAPH_SNAPSHOT]
        # graphId is inside the snapshot data, not at the event data level
        assert snap_events[0]["data"]["graphSnapshot"] == snapshot

    def test_graph_snapshot_non_dict_still_emitted(self):
        result = {"graphSnapshot": "some_string_snapshot"}
        events = tool_result_to_events(result)
        snap_events = [e for e in events if e["type"] == EventType.GRAPH_SNAPSHOT]
        assert len(snap_events) == 1

    def test_falsy_graph_snapshot_not_emitted(self):
        result = {"graphSnapshot": None}
        events = tool_result_to_events(result)
        snap_events = [e for e in events if e["type"] == EventType.GRAPH_SNAPSHOT]
        assert len(snap_events) == 0


class TestGraphPlanEvent:
    def test_plan_emitted(self):
        plan = {"root": {"searchName": "GenesByTextSearch"}}
        result = {
            "plan": plan,
            "graphId": "g1",
            "name": "Strategy",
            "recordType": "gene",
            "description": "Test strategy",
        }
        events = tool_result_to_events(result)
        plan_events = [e for e in events if e["type"] == EventType.GRAPH_PLAN]
        assert len(plan_events) == 1
        data = plan_events[0]["data"]
        assert data["plan"] == plan
        assert data["graphId"] == "g1"
        assert data["name"] == "Strategy"
        assert data["recordType"] == "gene"
        assert data["description"] == "Test strategy"

    def test_falsy_plan_not_emitted(self):
        result = {"plan": None}
        events = tool_result_to_events(result)
        plan_events = [e for e in events if e["type"] == EventType.GRAPH_PLAN]
        assert len(plan_events) == 0


class TestStrategyMetaEvent:
    def test_graph_id_with_name_emitted(self):
        result = {"graphId": "g1", "name": "My Strategy"}
        events = tool_result_to_events(result)
        meta_events = [e for e in events if e["type"] == EventType.STRATEGY_META]
        assert len(meta_events) == 1
        assert meta_events[0]["data"]["graphId"] == "g1"
        assert meta_events[0]["data"]["name"] == "My Strategy"

    def test_graph_id_with_description_emitted(self):
        result = {"graphId": "g1", "description": "A description"}
        events = tool_result_to_events(result)
        meta_events = [e for e in events if e["type"] == EventType.STRATEGY_META]
        assert len(meta_events) == 1

    def test_graph_id_with_record_type_emitted(self):
        result = {"graphId": "g1", "recordType": "gene"}
        events = tool_result_to_events(result)
        meta_events = [e for e in events if e["type"] == EventType.STRATEGY_META]
        assert len(meta_events) == 1

    def test_no_graph_id_no_meta(self):
        result = {"name": "Strategy", "description": "desc"}
        events = tool_result_to_events(result)
        meta_events = [e for e in events if e["type"] == EventType.STRATEGY_META]
        assert len(meta_events) == 0

    def test_graph_name_fallback(self):
        result = {"graphId": "g1", "name": None, "graphName": "Fallback Name"}
        events = tool_result_to_events(result)
        meta_events = [e for e in events if e["type"] == EventType.STRATEGY_META]
        # name=None is excluded by exclude_none; graphName is preserved
        assert "name" not in meta_events[0]["data"]
        assert meta_events[0]["data"]["graphName"] == "Fallback Name"


class TestGraphClearedEvent:
    def test_cleared_emitted(self):
        result = {"cleared": True, "graphId": "g1"}
        events = tool_result_to_events(result)
        cleared_events = [e for e in events if e["type"] == EventType.GRAPH_CLEARED]
        assert len(cleared_events) == 1
        assert cleared_events[0]["data"]["graphId"] == "g1"

    def test_cleared_false_not_emitted(self):
        result = {"cleared": False}
        events = tool_result_to_events(result)
        cleared_events = [e for e in events if e["type"] == EventType.GRAPH_CLEARED]
        assert len(cleared_events) == 0


class TestGeneSetCreatedEvent:
    def test_gene_set_created_dict_emitted(self):
        gene_set = {"id": "gs1", "name": "Kinases", "geneIds": ["g1", "g2"]}
        result = {"geneSetCreated": gene_set}
        events = tool_result_to_events(result)
        gs_events = [e for e in events if e["type"] == EventType.WORKBENCH_GENE_SET]
        assert len(gs_events) == 1
        assert gs_events[0]["data"]["geneSet"] == gene_set

    def test_gene_set_created_non_dict_not_emitted(self):
        result = {"geneSetCreated": "not a dict"}
        events = tool_result_to_events(result)
        gs_events = [e for e in events if e["type"] == EventType.WORKBENCH_GENE_SET]
        assert len(gs_events) == 0

    def test_gene_set_created_none_not_emitted(self):
        result = {"geneSetCreated": None}
        events = tool_result_to_events(result)
        gs_events = [e for e in events if e["type"] == EventType.WORKBENCH_GENE_SET]
        assert len(gs_events) == 0


class TestStrategyLinkEvent:
    def test_wdk_strategy_id_emitted(self):
        result = {
            "wdkStrategyId": 12345,
            "graphId": "g1",
            "wdkUrl": "https://plasmodb.org/...",
            "name": "Kinases",
            "description": "desc",
        }
        events = tool_result_to_events(result)
        link_events = [e for e in events if e["type"] == EventType.STRATEGY_LINK]
        assert len(link_events) == 1
        data = link_events[0]["data"]
        assert data["wdkStrategyId"] == 12345
        assert data["graphId"] == "g1"
        assert data["wdkUrl"] == "https://plasmodb.org/..."
        assert data["name"] == "Kinases"

    def test_wdk_strategy_id_zero_emitted(self):
        # 0 is not None, so it should be emitted
        result = {"wdkStrategyId": 0}
        events = tool_result_to_events(result)
        link_events = [e for e in events if e["type"] == EventType.STRATEGY_LINK]
        assert len(link_events) == 1

    def test_wdk_strategy_id_none_not_emitted(self):
        result = {"wdkStrategyId": None}
        events = tool_result_to_events(result)
        link_events = [e for e in events if e["type"] == EventType.STRATEGY_LINK]
        assert len(link_events) == 0

    def test_wdk_strategy_id_absent_not_emitted(self):
        result = {"graphId": "g1"}
        events = tool_result_to_events(result)
        link_events = [e for e in events if e["type"] == EventType.STRATEGY_LINK]
        assert len(link_events) == 0


class TestMultipleEventsCombined:
    def test_complex_result_emits_multiple_events(self):
        result = {
            "stepId": "s1",
            "graphId": "g1",
            "name": "Combined Strategy",
            "recordType": "gene",
            "citations": [{"url": "http://x.com"}],
            "reasoning": "Because of kinases.",
            "wdkStrategyId": 999,
        }
        events = tool_result_to_events(result)
        types = [e["type"] for e in events]
        assert EventType.CITATIONS in types
        assert EventType.REASONING in types
        assert EventType.STRATEGY_UPDATE in types
        assert EventType.STRATEGY_META in types
        assert EventType.STRATEGY_LINK in types

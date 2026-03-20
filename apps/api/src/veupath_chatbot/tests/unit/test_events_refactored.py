"""Unit tests for individual event extractors in services.chat.events.

Tests each _extract_* function in isolation, plus the registry-based
tool_result_to_events dispatcher.
"""

from typing import ClassVar

from veupath_chatbot.services.chat.events import (
    CITATIONS,
    EXECUTOR_BUILD_REQUEST,
    GRAPH_CLEARED,
    GRAPH_PLAN,
    GRAPH_SNAPSHOT,
    PLANNING_ARTIFACT,
    REASONING,
    STRATEGY_LINK,
    STRATEGY_META,
    STRATEGY_UPDATE,
    WORKBENCH_GENE_SET,
    _extract_citations,
    _extract_cleared,
    _extract_conversation_title,
    _extract_executor_build_request,
    _extract_gene_set_created,
    _extract_graph_plan,
    _extract_graph_snapshot,
    _extract_planning_artifact,
    _extract_reasoning,
    _extract_step_update,
    _extract_strategy_link,
    _extract_strategy_meta,
    tool_result_to_events,
)

# ---------------------------------------------------------------------------
# _extract_citations
# ---------------------------------------------------------------------------


class TestExtractCitations:
    def test_valid_citations_returns_event(self):
        result = {"citations": [{"url": "http://example.com"}]}
        event = _extract_citations(result, get_graph=None)
        assert event is not None
        assert event["type"] == CITATIONS
        assert event["data"]["citations"] == [{"url": "http://example.com"}]

    def test_empty_list_returns_none(self):
        assert _extract_citations({"citations": []}, get_graph=None) is None

    def test_non_list_returns_none(self):
        assert _extract_citations({"citations": "string"}, get_graph=None) is None

    def test_absent_returns_none(self):
        assert _extract_citations({}, get_graph=None) is None

    def test_none_value_returns_none(self):
        assert _extract_citations({"citations": None}, get_graph=None) is None


# ---------------------------------------------------------------------------
# _extract_planning_artifact
# ---------------------------------------------------------------------------


class TestExtractPlanningArtifact:
    def test_truthy_artifact_returns_event(self):
        result = {"planningArtifact": {"id": "art1"}}
        event = _extract_planning_artifact(result, get_graph=None)
        assert event is not None
        assert event["type"] == PLANNING_ARTIFACT
        assert event["data"]["planningArtifact"] == {"id": "art1"}

    def test_falsy_values_return_none(self):
        for val in [None, "", 0, False, {}, []]:
            assert (
                _extract_planning_artifact({"planningArtifact": val}, get_graph=None)
                is None
            )

    def test_absent_returns_none(self):
        assert _extract_planning_artifact({}, get_graph=None) is None


# ---------------------------------------------------------------------------
# _extract_reasoning
# ---------------------------------------------------------------------------


class TestExtractReasoning:
    def test_valid_reasoning_returns_event(self):
        result = {"reasoning": "The user wants kinases."}
        event = _extract_reasoning(result, get_graph=None)
        assert event is not None
        assert event["type"] == REASONING
        assert event["data"]["reasoning"] == "The user wants kinases."

    def test_whitespace_only_returns_none(self):
        assert _extract_reasoning({"reasoning": "   "}, get_graph=None) is None

    def test_empty_string_returns_none(self):
        assert _extract_reasoning({"reasoning": ""}, get_graph=None) is None

    def test_non_string_returns_none(self):
        assert _extract_reasoning({"reasoning": 42}, get_graph=None) is None

    def test_absent_returns_none(self):
        assert _extract_reasoning({}, get_graph=None) is None


# ---------------------------------------------------------------------------
# _extract_conversation_title
# ---------------------------------------------------------------------------


class TestExtractConversationTitle:
    def test_valid_title_returns_strategy_meta(self):
        result = {"conversationTitle": "My Strategy"}
        event = _extract_conversation_title(result, get_graph=None)
        assert event is not None
        assert event["type"] == STRATEGY_META
        assert event["data"]["name"] == "My Strategy"

    def test_strips_whitespace(self):
        result = {"conversationTitle": "  Trimmed  "}
        event = _extract_conversation_title(result, get_graph=None)
        assert event is not None
        assert event["data"]["name"] == "Trimmed"

    def test_whitespace_only_returns_none(self):
        assert (
            _extract_conversation_title({"conversationTitle": "   "}, get_graph=None)
            is None
        )

    def test_non_string_returns_none(self):
        assert (
            _extract_conversation_title({"conversationTitle": 123}, get_graph=None)
            is None
        )

    def test_absent_returns_none(self):
        assert _extract_conversation_title({}, get_graph=None) is None


# ---------------------------------------------------------------------------
# _extract_executor_build_request
# ---------------------------------------------------------------------------


class TestExtractExecutorBuildRequest:
    def test_dict_returns_event(self):
        req = {"steps": ["a", "b"]}
        result = {"executorBuildRequest": req}
        event = _extract_executor_build_request(result, get_graph=None)
        assert event is not None
        assert event["type"] == EXECUTOR_BUILD_REQUEST
        assert event["data"]["executorBuildRequest"] == req

    def test_non_dict_returns_none(self):
        assert (
            _extract_executor_build_request(
                {"executorBuildRequest": "str"}, get_graph=None
            )
            is None
        )

    def test_absent_returns_none(self):
        assert _extract_executor_build_request({}, get_graph=None) is None


# ---------------------------------------------------------------------------
# _extract_step_update
# ---------------------------------------------------------------------------


class TestExtractStepUpdate:
    def test_step_id_without_get_graph(self):
        result = {"stepId": "s1", "graphId": "g1"}
        event = _extract_step_update(result, get_graph=None)
        assert event is not None
        assert event["type"] == STRATEGY_UPDATE
        assert event["data"]["graphId"] == "g1"
        assert event["data"]["step"] == result
        assert event["data"]["allSteps"] == []

    def test_step_id_with_get_graph_returning_none(self):
        result = {"stepId": "s1", "graphId": "g1"}
        event = _extract_step_update(result, get_graph=lambda gid: None)
        assert event is not None
        assert event["data"]["allSteps"] == []

    def test_step_id_with_get_graph_returning_graph(self):
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
        event = _extract_step_update(result, get_graph=lambda gid: graph)
        assert event is not None
        all_steps = event["data"]["allSteps"]
        assert len(all_steps) == 2
        step_ids = {s["stepId"] for s in all_steps}
        assert step_ids == {"s1", "s2"}

    def test_non_string_graph_id_coerced_to_none(self):
        result = {"stepId": "s1", "graphId": 999}
        event = _extract_step_update(result, get_graph=None)
        assert event is not None
        assert event["data"]["graphId"] is None

    def test_no_step_id_returns_none(self):
        result = {"graphId": "g1"}
        event = _extract_step_update(result, get_graph=None)
        assert event is None


# ---------------------------------------------------------------------------
# _extract_graph_snapshot
# ---------------------------------------------------------------------------


class TestExtractGraphSnapshot:
    def test_dict_snapshot_with_graph_id(self):
        snapshot = {"steps": [], "graphId": "g1"}
        result = {"graphSnapshot": snapshot}
        event = _extract_graph_snapshot(result, get_graph=None)
        assert event is not None
        assert event["type"] == GRAPH_SNAPSHOT
        assert event["data"]["graphId"] == "g1"
        assert event["data"]["graphSnapshot"] == snapshot

    def test_fallback_to_result_graph_id(self):
        snapshot = {"steps": []}
        result = {"graphSnapshot": snapshot, "graphId": "g_fallback"}
        event = _extract_graph_snapshot(result, get_graph=None)
        assert event is not None
        assert event["data"]["graphId"] == "g_fallback"

    def test_non_dict_snapshot_still_emitted(self):
        result = {"graphSnapshot": "some_string"}
        event = _extract_graph_snapshot(result, get_graph=None)
        assert event is not None
        assert event["data"]["graphSnapshot"] == "some_string"

    def test_falsy_snapshot_returns_none(self):
        assert _extract_graph_snapshot({"graphSnapshot": None}, get_graph=None) is None
        assert _extract_graph_snapshot({"graphSnapshot": {}}, get_graph=None) is None

    def test_non_string_graph_id_in_snapshot_coerced_to_none(self):
        snapshot = {"steps": [], "graphId": 42}
        result = {"graphSnapshot": snapshot}
        event = _extract_graph_snapshot(result, get_graph=None)
        assert event is not None
        assert event["data"]["graphId"] is None

    def test_skipped_when_auto_build_succeeded(self):
        """When autoBuild.ok is True, the auto-build hook already emitted
        a graph_snapshot with WDK step IDs. Extracting the tool result's
        pre-build snapshot would overwrite it with stale data."""
        result = {
            "graphSnapshot": {
                "steps": [{"id": "s1", "isBuilt": False}],
                "graphId": "g1",
            },
            "autoBuild": {"ok": True, "wdkStrategyId": 999},
        }
        event = _extract_graph_snapshot(result, get_graph=None)
        assert event is None

    def test_not_skipped_when_auto_build_failed(self):
        """When autoBuild.ok is False, the tool result snapshot is the only
        one — it should still be extracted."""
        snapshot = {"steps": [{"id": "s1"}], "graphId": "g1"}
        result = {
            "graphSnapshot": snapshot,
            "autoBuild": {"ok": False, "error": "WDK down"},
        }
        event = _extract_graph_snapshot(result, get_graph=None)
        assert event is not None
        assert event["type"] == GRAPH_SNAPSHOT

    def test_not_skipped_when_auto_build_skipped(self):
        """When autoBuild was skipped (multiple roots), the tool result
        snapshot should still be extracted."""
        snapshot = {"steps": [{"id": "s1"}], "graphId": "g1"}
        result = {
            "graphSnapshot": snapshot,
            "autoBuild": {"ok": False, "skipped": True, "reason": "multiple_roots"},
        }
        event = _extract_graph_snapshot(result, get_graph=None)
        assert event is not None
        assert event["type"] == GRAPH_SNAPSHOT

    def test_not_skipped_without_auto_build(self):
        """Without autoBuild, normal extraction should work."""
        snapshot = {"steps": [{"id": "s1"}], "graphId": "g1"}
        result = {"graphSnapshot": snapshot}
        event = _extract_graph_snapshot(result, get_graph=None)
        assert event is not None
        assert event["type"] == GRAPH_SNAPSHOT


# ---------------------------------------------------------------------------
# _extract_graph_plan
# ---------------------------------------------------------------------------


class TestExtractGraphPlan:
    def test_valid_plan_returns_event(self):
        plan = {"root": {"searchName": "GenesByTextSearch"}}
        result = {
            "plan": plan,
            "graphId": "g1",
            "name": "Strategy",
            "recordType": "gene",
            "description": "Test",
        }
        event = _extract_graph_plan(result, get_graph=None)
        assert event is not None
        assert event["type"] == GRAPH_PLAN
        assert event["data"]["plan"] == plan
        assert event["data"]["graphId"] == "g1"
        assert event["data"]["name"] == "Strategy"
        assert event["data"]["recordType"] == "gene"

    def test_falsy_plan_returns_none(self):
        assert _extract_graph_plan({"plan": None}, get_graph=None) is None
        assert _extract_graph_plan({"plan": {}}, get_graph=None) is None
        assert _extract_graph_plan({"plan": []}, get_graph=None) is None

    def test_absent_plan_returns_none(self):
        assert _extract_graph_plan({}, get_graph=None) is None


# ---------------------------------------------------------------------------
# _extract_strategy_meta
# ---------------------------------------------------------------------------


class TestExtractStrategyMeta:
    def test_graph_id_with_name(self):
        result = {"graphId": "g1", "name": "My Strategy"}
        event = _extract_strategy_meta(result, get_graph=None)
        assert event is not None
        assert event["type"] == STRATEGY_META
        assert event["data"]["graphId"] == "g1"
        assert event["data"]["name"] == "My Strategy"

    def test_graph_id_with_description(self):
        result = {"graphId": "g1", "description": "A description"}
        event = _extract_strategy_meta(result, get_graph=None)
        assert event is not None

    def test_graph_id_with_record_type(self):
        result = {"graphId": "g1", "recordType": "gene"}
        event = _extract_strategy_meta(result, get_graph=None)
        assert event is not None

    def test_no_graph_id_returns_none(self):
        result = {"name": "Strategy"}
        event = _extract_strategy_meta(result, get_graph=None)
        assert event is None

    def test_graph_id_without_meta_fields_returns_none(self):
        result = {"graphId": "g1"}
        event = _extract_strategy_meta(result, get_graph=None)
        assert event is None

    def test_graph_name_fallback(self):
        result = {"graphId": "g1", "name": None, "graphName": "Fallback"}
        event = _extract_strategy_meta(result, get_graph=None)
        assert event is not None
        assert event["data"]["name"] == "Fallback"

    def test_falsy_graph_id_returns_none(self):
        result = {"graphId": "", "name": "Strategy"}
        event = _extract_strategy_meta(result, get_graph=None)
        assert event is None


# ---------------------------------------------------------------------------
# _extract_cleared
# ---------------------------------------------------------------------------


class TestExtractCleared:
    def test_truthy_cleared_returns_event(self):
        result = {"cleared": True, "graphId": "g1"}
        event = _extract_cleared(result, get_graph=None)
        assert event is not None
        assert event["type"] == GRAPH_CLEARED
        assert event["data"]["graphId"] == "g1"

    def test_falsy_cleared_returns_none(self):
        assert _extract_cleared({"cleared": False}, get_graph=None) is None
        assert _extract_cleared({"cleared": None}, get_graph=None) is None
        assert _extract_cleared({"cleared": 0}, get_graph=None) is None
        assert _extract_cleared({"cleared": ""}, get_graph=None) is None

    def test_absent_returns_none(self):
        assert _extract_cleared({}, get_graph=None) is None


# ---------------------------------------------------------------------------
# _extract_gene_set_created
# ---------------------------------------------------------------------------


class TestExtractGeneSetCreated:
    def test_dict_gene_set_returns_event(self):
        gene_set = {"id": "gs1", "name": "Kinases"}
        result = {"geneSetCreated": gene_set}
        event = _extract_gene_set_created(result, get_graph=None)
        assert event is not None
        assert event["type"] == WORKBENCH_GENE_SET
        assert event["data"]["geneSet"] == gene_set

    def test_non_dict_returns_none(self):
        assert (
            _extract_gene_set_created({"geneSetCreated": "str"}, get_graph=None) is None
        )

    def test_none_returns_none(self):
        assert (
            _extract_gene_set_created({"geneSetCreated": None}, get_graph=None) is None
        )

    def test_empty_dict_still_emitted(self):
        # isinstance({}, dict) is True, so empty dict IS emitted
        event = _extract_gene_set_created({"geneSetCreated": {}}, get_graph=None)
        assert event is not None


# ---------------------------------------------------------------------------
# _extract_strategy_link
# ---------------------------------------------------------------------------


class TestExtractStrategyLink:
    def test_valid_wdk_strategy_id_returns_event(self):
        result = {
            "wdkStrategyId": 12345,
            "graphId": "g1",
            "wdkUrl": "https://plasmodb.org/...",
            "name": "Kinases",
            "description": "desc",
        }
        event = _extract_strategy_link(result, get_graph=None)
        assert event is not None
        assert event["type"] == STRATEGY_LINK
        assert event["data"]["wdkStrategyId"] == 12345
        assert event["data"]["graphId"] == "g1"

    def test_zero_wdk_strategy_id_emitted(self):
        result = {"wdkStrategyId": 0}
        event = _extract_strategy_link(result, get_graph=None)
        assert event is not None

    def test_none_wdk_strategy_id_returns_none(self):
        result = {"wdkStrategyId": None}
        event = _extract_strategy_link(result, get_graph=None)
        assert event is None

    def test_absent_returns_none(self):
        result = {"graphId": "g1"}
        event = _extract_strategy_link(result, get_graph=None)
        assert event is None


# ---------------------------------------------------------------------------
# Registry-based tool_result_to_events
# ---------------------------------------------------------------------------


class TestRegistryDispatch:
    def test_unknown_keys_produce_no_events(self):
        """Keys not matching any extractor should produce no events."""
        result = {"unknownKey": "value", "anotherUnknown": 42}
        events = tool_result_to_events(result)
        assert events == []

    def test_combined_result_produces_correct_events(self):
        """Multiple extractors fire from a single result."""
        result = {
            "citations": [{"url": "http://x.com"}],
            "reasoning": "Because science",
            "cleared": True,
            "graphId": "g1",
        }
        events = tool_result_to_events(result)
        types = [e["type"] for e in events]
        assert CITATIONS in types
        assert REASONING in types
        assert GRAPH_CLEARED in types

    def test_ordering_matches_extractor_registration(self):
        """Events should appear in the order extractors are registered."""
        result = {
            "citations": [{"url": "http://x.com"}],
            "reasoning": "reasoning text",
            "wdkStrategyId": 42,
        }
        events = tool_result_to_events(result)
        types = [e["type"] for e in events]
        assert types.index(CITATIONS) < types.index(REASONING)
        assert types.index(REASONING) < types.index(STRATEGY_LINK)

    def test_non_dict_returns_empty(self):
        assert tool_result_to_events("not a dict") == []
        assert tool_result_to_events(42) == []
        assert tool_result_to_events([1, 2]) == []

    def test_empty_dict_returns_empty(self):
        assert tool_result_to_events({}) == []

    def test_get_graph_passed_to_extractors(self):
        """get_graph callback should reach _extract_step_update."""

        class MockStep:
            display_name = "Step"

            def infer_kind(self):
                return "search"

        class MockGraph:
            steps: ClassVar[dict] = {"s1": MockStep()}

        result = {"stepId": "s1", "graphId": "g1"}
        events = tool_result_to_events(result, get_graph=lambda gid: MockGraph())
        update_events = [e for e in events if e["type"] == STRATEGY_UPDATE]
        assert len(update_events) == 1
        assert len(update_events[0]["data"]["allSteps"]) == 1

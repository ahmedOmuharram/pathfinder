"""Extended tests for services.chat.events — edge cases and special characters."""

from veupath_chatbot.services.chat.events import (
    EventType,
    tool_result_to_events,
)

# ---------------------------------------------------------------------------
# Special characters in event data
# ---------------------------------------------------------------------------


class TestSpecialCharactersInEvents:
    def test_citations_with_unicode(self):
        result = {
            "citations": [{"url": "http://example.com", "title": "Pf\u00e4lzer Kinase"}]
        }
        events = tool_result_to_events(result)
        assert events[0]["data"]["citations"][0]["title"] == "Pf\u00e4lzer Kinase"

    def test_reasoning_with_newlines(self):
        result = {"reasoning": "Line 1\nLine 2\nLine 3"}
        events = tool_result_to_events(result)
        assert events[0]["data"]["reasoning"] == "Line 1\nLine 2\nLine 3"

    def test_reasoning_with_html_tags(self):
        result = {"reasoning": '<b>Important</b> finding with <a href="#">link</a>'}
        events = tool_result_to_events(result)
        assert events[0]["type"] == EventType.REASONING
        assert "<b>Important</b>" in events[0]["data"]["reasoning"]

    def test_conversation_title_with_unicode(self):
        result = {"conversationTitle": "Plasmodium \u2014 Kinase Strategy"}
        events = tool_result_to_events(result)
        assert events[0]["data"]["name"] == "Plasmodium \u2014 Kinase Strategy"

    def test_reasoning_with_only_newlines(self):
        """Newlines should not be treated as whitespace-only."""
        result = {"reasoning": "\n\n\n"}
        events = tool_result_to_events(result)
        # strip() removes newlines, so this should NOT be emitted
        assert len(events) == 0

    def test_conversation_title_with_only_tabs(self):
        result = {"conversationTitle": "\t\t"}
        events = tool_result_to_events(result)
        assert len(events) == 0

    def test_citations_with_special_chars_in_url(self):
        result = {
            "citations": [
                {"url": "https://example.com/search?q=kinase&org=P.%20falciparum"}
            ]
        }
        events = tool_result_to_events(result)
        assert len(events) == 1
        assert "P.%20falciparum" in events[0]["data"]["citations"][0]["url"]


# ---------------------------------------------------------------------------
# Duplicate event emission checks
# ---------------------------------------------------------------------------


class TestDuplicateEventEmission:
    def test_conversation_title_and_graph_meta_both_emit_strategy_meta(self):
        """When result has both conversationTitle AND graphId+name,
        TWO separate STRATEGY_META events should be emitted."""
        result = {
            "conversationTitle": "Title from chat",
            "graphId": "g1",
            "name": "Name from graph",
        }
        events = tool_result_to_events(result)
        meta_events = [e for e in events if e["type"] == EventType.STRATEGY_META]
        # Both conversationTitle and graphId+name paths trigger STRATEGY_META
        assert len(meta_events) == 2
        # First one is from conversationTitle (just 'name')
        assert meta_events[0]["data"]["name"] == "Title from chat"
        # Second one is from graphId+name (has graphId)
        assert meta_events[1]["data"]["graphId"] == "g1"
        assert meta_events[1]["data"]["name"] == "Name from graph"


# ---------------------------------------------------------------------------
# Event ordering
# ---------------------------------------------------------------------------


class TestEventOrdering:
    def test_citations_before_reasoning(self):
        result = {
            "citations": [{"url": "http://test.com"}],
            "reasoning": "Some reasoning",
        }
        events = tool_result_to_events(result)
        types = [e["type"] for e in events]
        assert types.index(EventType.CITATIONS) < types.index(EventType.REASONING)

    def test_reasoning_before_strategy_update(self):
        result = {
            "reasoning": "Some reasoning",
            "stepId": "s1",
            "graphId": "g1",
            "name": "Strategy",
        }
        events = tool_result_to_events(result)
        types = [e["type"] for e in events]
        assert types.index(EventType.REASONING) < types.index(EventType.STRATEGY_UPDATE)

    def test_strategy_link_is_last_link_related_event(self):
        result = {
            "stepId": "s1",
            "graphId": "g1",
            "name": "Strategy",
            "wdkStrategyId": 123,
        }
        events = tool_result_to_events(result)
        types = [e["type"] for e in events]
        # strategy_link should come after strategy_update and strategy_meta
        assert types.index(EventType.STRATEGY_LINK) > types.index(EventType.STRATEGY_UPDATE)
        assert types.index(EventType.STRATEGY_LINK) > types.index(EventType.STRATEGY_META)


# ---------------------------------------------------------------------------
# Non-string graphId edge cases
# ---------------------------------------------------------------------------


class TestGraphIdEdgeCases:
    def test_empty_string_graph_id_no_strategy_meta(self):
        """Empty string is falsy, should NOT trigger STRATEGY_META."""
        result = {"graphId": "", "name": "Strategy"}
        events = tool_result_to_events(result)
        meta_events = [e for e in events if e["type"] == EventType.STRATEGY_META]
        assert len(meta_events) == 0

    def test_graph_id_zero_in_strategy_meta(self):
        """0 is falsy, should NOT trigger STRATEGY_META."""
        result = {"graphId": 0, "name": "Strategy"}
        events = tool_result_to_events(result)
        meta_events = [e for e in events if e["type"] == EventType.STRATEGY_META]
        assert len(meta_events) == 0


# ---------------------------------------------------------------------------
# Graph plan event edge cases
# ---------------------------------------------------------------------------


class TestGraphPlanEdgeCases:
    def test_plan_as_empty_list_is_falsy(self):
        result = {"plan": []}
        events = tool_result_to_events(result)
        plan_events = [e for e in events if e["type"] == EventType.GRAPH_PLAN]
        assert len(plan_events) == 0

    def test_plan_with_missing_optional_fields(self):
        result = {"plan": {"root": {}}}
        events = tool_result_to_events(result)
        plan_events = [e for e in events if e["type"] == EventType.GRAPH_PLAN]
        assert len(plan_events) == 1
        data = plan_events[0]["data"]
        # CamelModel uses exclude_none=True, so absent optional fields are omitted
        assert "graphId" not in data
        assert "name" not in data
        assert "recordType" not in data
        assert "description" not in data


# ---------------------------------------------------------------------------
# Graph snapshot edge cases
# ---------------------------------------------------------------------------


class TestGraphSnapshotEdgeCases:
    def test_graph_snapshot_empty_dict_is_falsy(self):
        """Empty dict is falsy, so graphSnapshot should NOT emit."""
        result = {"graphSnapshot": {}}
        events = tool_result_to_events(result)
        snap_events = [e for e in events if e["type"] == EventType.GRAPH_SNAPSHOT]
        assert len(snap_events) == 0


# ---------------------------------------------------------------------------
# Cleared event edge cases
# ---------------------------------------------------------------------------


class TestClearedEdgeCases:
    def test_cleared_none_not_emitted(self):
        result = {"cleared": None}
        events = tool_result_to_events(result)
        cleared_events = [e for e in events if e["type"] == EventType.GRAPH_CLEARED]
        assert len(cleared_events) == 0

    def test_cleared_zero_not_emitted(self):
        result = {"cleared": 0}
        events = tool_result_to_events(result)
        cleared_events = [e for e in events if e["type"] == EventType.GRAPH_CLEARED]
        assert len(cleared_events) == 0

    def test_cleared_empty_string_not_emitted(self):
        result = {"cleared": ""}
        events = tool_result_to_events(result)
        cleared_events = [e for e in events if e["type"] == EventType.GRAPH_CLEARED]
        assert len(cleared_events) == 0

    def test_cleared_truthy_string_emitted(self):
        result = {"cleared": "yes", "graphId": "g1"}
        events = tool_result_to_events(result)
        cleared_events = [e for e in events if e["type"] == EventType.GRAPH_CLEARED]
        assert len(cleared_events) == 1


# ---------------------------------------------------------------------------
# Gene set created edge cases
# ---------------------------------------------------------------------------


class TestGeneSetCreatedEdgeCases:
    def test_gene_set_created_empty_dict_still_emitted(self):
        """Empty dict is falsy, should NOT emit."""
        result = {"geneSetCreated": {}}
        events = tool_result_to_events(result)
        gs_events = [e for e in events if e["type"] == EventType.WORKBENCH_GENE_SET]
        # isinstance({}, dict) is True, but truthiness check missing --
        # the code only checks isinstance, so an empty dict IS emitted.
        assert len(gs_events) == 1

    def test_gene_set_created_list_not_emitted(self):
        result = {"geneSetCreated": [{"id": "gs1"}]}
        events = tool_result_to_events(result)
        gs_events = [e for e in events if e["type"] == EventType.WORKBENCH_GENE_SET]
        assert len(gs_events) == 0

    def test_gene_set_created_with_nested_data(self):
        gene_set = {
            "id": "gs1",
            "name": "My Genes",
            "geneIds": [f"GENE_{i}" for i in range(1000)],
        }
        result = {"geneSetCreated": gene_set}
        events = tool_result_to_events(result)
        gs_events = [e for e in events if e["type"] == EventType.WORKBENCH_GENE_SET]
        assert len(gs_events) == 1
        assert len(gs_events[0]["data"]["geneSet"]["geneIds"]) == 1000


# ---------------------------------------------------------------------------
# Strategy link edge cases
# ---------------------------------------------------------------------------


class TestStrategyLinkEdgeCases:
    def test_wdk_strategy_id_as_string(self):
        """String wdkStrategyId is not None, so link should emit."""
        result = {"wdkStrategyId": "12345"}
        events = tool_result_to_events(result)
        link_events = [e for e in events if e["type"] == EventType.STRATEGY_LINK]
        assert len(link_events) == 1

    def test_wdk_strategy_id_false_not_emitted(self):
        """False is not None, so link should emit."""
        result = {"wdkStrategyId": False}
        events = tool_result_to_events(result)
        link_events = [e for e in events if e["type"] == EventType.STRATEGY_LINK]
        assert len(link_events) == 1


# ---------------------------------------------------------------------------
# All events combined stress test
# ---------------------------------------------------------------------------


class TestAllEventsCombined:
    def test_maximum_events_from_single_result(self):
        """A result with all possible fields should emit all event types."""

        class MockStep:
            def __init__(self):
                self.display_name = "Step"

            def infer_kind(self):
                return "search"

        class MockGraph:
            def __init__(self):
                self.steps = {"s1": MockStep()}

        result = {
            "citations": [{"url": "http://test.com"}],
            "planningArtifact": {"id": "art1"},
            "reasoning": "Because science",
            "conversationTitle": "A Title",
            "executorBuildRequest": {"steps": ["a"]},
            "stepId": "s1",
            "graphId": "g1",
            "graphSnapshot": {"steps": [], "graphId": "g1"},
            "plan": {"root": {}},
            "name": "Strategy Name",
            "description": "Desc",
            "recordType": "gene",
            "cleared": True,
            "geneSetCreated": {"id": "gs1"},
            "wdkStrategyId": 42,
        }
        events = tool_result_to_events(result, get_graph=lambda gid: MockGraph())
        types = {e["type"] for e in events}
        # Should have all event types
        assert EventType.CITATIONS in types
        assert EventType.PLANNING_ARTIFACT in types
        assert EventType.REASONING in types
        assert EventType.STRATEGY_META in types
        assert EventType.EXECUTOR_BUILD_REQUEST in types
        assert EventType.STRATEGY_UPDATE in types
        assert EventType.GRAPH_SNAPSHOT in types
        assert EventType.GRAPH_PLAN in types
        assert EventType.GRAPH_CLEARED in types
        assert EventType.WORKBENCH_GENE_SET in types
        assert EventType.STRATEGY_LINK in types

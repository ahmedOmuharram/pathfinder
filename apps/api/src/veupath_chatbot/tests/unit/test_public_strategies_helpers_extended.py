"""Extended tests for public_strategies_helpers.py -- edge cases not covered by existing tests."""

from veupath_chatbot.integrations.vectorstore.ingest.public_strategies_helpers import (
    EMBED_TEXT_MAX_CHARS,
    embedding_text_for_example,
    full_strategy_payload,
    iter_compact_steps,
    simplify_strategy_details,
    truncate,
)


class TestTruncateEdgeCases:
    def test_exact_max_chars_no_truncation(self) -> None:
        s = "x" * 100
        assert truncate(s, max_chars=100) == s

    def test_one_over_max_truncates(self) -> None:
        s = "x" * 101
        result = truncate(s, max_chars=100)
        assert result.endswith(("...(truncated)", "…(truncated)"))
        assert len(result) <= 100

    def test_empty_string(self) -> None:
        assert truncate("", max_chars=10) == ""

    def test_max_chars_zero(self) -> None:
        result = truncate("hello", max_chars=0)
        assert "\u2026(truncated)" in result

    def test_very_small_max_chars(self) -> None:
        # max_chars=5 means s[:max(0, 5-20)] = s[:0] + suffix
        result = truncate("hello world", max_chars=5)
        assert result == "\u2026(truncated)"


class TestIterCompactSteps:
    def test_none_input(self) -> None:
        assert iter_compact_steps(None) == []

    def test_non_dict_input(self) -> None:
        assert iter_compact_steps("not-a-dict") == []

    def test_single_step(self) -> None:
        tree = {"stepId": "1", "searchName": "test"}
        steps = iter_compact_steps(tree)
        assert len(steps) == 1

    def test_deep_tree(self) -> None:
        tree = {
            "stepId": "root",
            "primaryInput": {
                "stepId": "mid",
                "primaryInput": {"stepId": "leaf"},
            },
        }
        steps = iter_compact_steps(tree)
        ids = {s.get("stepId") for s in steps if isinstance(s, dict)}
        assert ids == {"root", "mid", "leaf"}

    def test_only_primary_input(self) -> None:
        tree = {"stepId": "root", "primaryInput": {"stepId": "a"}}
        steps = iter_compact_steps(tree)
        assert len(steps) == 2

    def test_only_secondary_input(self) -> None:
        tree = {"stepId": "root", "secondaryInput": {"stepId": "b"}}
        steps = iter_compact_steps(tree)
        assert len(steps) == 2


class TestSimplifyStrategyDetails:
    def test_missing_steps_map(self) -> None:
        details = {
            "recordClassName": "Gene",
            "rootStepId": 1,
            "stepTree": {"stepId": "1"},
            "steps": {},
        }
        compact = simplify_strategy_details(details)
        assert compact["stepTree"]["searchName"] is None
        assert compact["stepTree"]["displayName"] is None
        assert compact["stepTree"]["operator"] is None

    def test_no_step_tree(self) -> None:
        details = {
            "recordClassName": "Gene",
            "rootStepId": 1,
            "stepTree": "not-a-dict",
            "steps": {},
        }
        compact = simplify_strategy_details(details)
        assert compact["stepTree"] is None

    def test_nested_step_tree_is_simplified(self) -> None:
        details = {
            "recordClassName": "Gene",
            "rootStepId": 1,
            "stepTree": {
                "stepId": "2",
                "primaryInput": {"stepId": "1"},
            },
            "steps": {
                "1": {
                    "searchName": "GenesByText",
                    "displayName": "Text Search",
                    "searchConfig": {"parameters": {"text": "kinase"}},
                },
                "2": {
                    "searchName": "GenesByLocation",
                    "displayName": "Location",
                    "searchConfig": {
                        "parameters": {"bq_operator": "INTERSECT", "loc": "chr1"}
                    },
                },
            },
        }
        compact = simplify_strategy_details(details)
        root = compact["stepTree"]
        assert root["searchName"] == "GenesByLocation"
        assert root["operator"] == "INTERSECT"
        primary = root["primaryInput"]
        assert primary["searchName"] == "GenesByText"
        assert primary["parameters"] == {"text": "kinase"}

    def test_no_search_config(self) -> None:
        details = {
            "recordClassName": "Gene",
            "rootStepId": 1,
            "stepTree": {"stepId": "1"},
            "steps": {
                "1": {
                    "searchName": "test",
                    "displayName": "Test",
                }
            },
        }
        compact = simplify_strategy_details(details)
        assert compact["stepTree"]["operator"] is None
        assert compact["stepTree"]["parameters"] == {}


class TestFullStrategyPayload:
    def test_missing_fields_return_none(self) -> None:
        payload = full_strategy_payload({})
        assert payload["recordClassName"] is None
        assert payload["rootStepId"] is None
        assert payload["stepTree"] is None
        assert payload["steps"] is None


class TestEmbeddingTextForExample:
    def test_empty_compact(self) -> None:
        text = embedding_text_for_example(name="N", description="D", compact={})
        assert "N" in text
        assert "D" in text

    def test_truncated_to_max_chars(self) -> None:
        # Create compact with many steps to generate long text
        step_tree = {
            "searchName": "VeryLongSearchName" * 100,
            "parameters": {f"param_{i}": "x" * 300 for i in range(60)},
        }
        compact = {"recordClassName": "Gene", "stepTree": step_tree}
        text = embedding_text_for_example(
            name="Name", description="Description", compact=compact
        )
        assert len(text) <= EMBED_TEXT_MAX_CHARS

    def test_step_with_no_search_name(self) -> None:
        compact = {
            "recordClassName": "Gene",
            "stepTree": {"parameters": {"k": "v"}},
        }
        text = embedding_text_for_example(name="N", description="D", compact=compact)
        assert "k=" in text

    def test_step_with_operator(self) -> None:
        compact = {
            "stepTree": {
                "searchName": "S1",
                "operator": "INTERSECT",
                "parameters": {},
            },
        }
        text = embedding_text_for_example(name="N", description="D", compact=compact)
        assert "INTERSECT" in text
        assert "S1" in text

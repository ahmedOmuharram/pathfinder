from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.vectorstore.ingest.public_strategies_helpers import (
    backoff_delay_seconds,
    embedding_text_for_example,
    full_strategy_payload,
    iter_compact_steps,
    simplify_strategy_details,
    truncate,
)


def test_backoff_delay_seconds_caps_at_8() -> None:
    assert backoff_delay_seconds(1) == 1
    assert backoff_delay_seconds(2) == 2
    assert backoff_delay_seconds(3) == 4
    assert backoff_delay_seconds(4) == 8
    assert backoff_delay_seconds(5) == 8


def test_truncate_leaves_short_string_unchanged() -> None:
    assert truncate("abc", max_chars=3) == "abc"


def test_truncate_adds_suffix_when_truncating() -> None:
    out = truncate("x" * 100, max_chars=50)
    assert out.endswith("…(truncated)")


def test_iter_compact_steps_walks_inputs() -> None:
    tree: JSONObject = {
        "stepId": "root",
        "primaryInput": {"stepId": "a"},
        "secondaryInput": {"stepId": "b", "input": {"stepId": "c"}},
    }
    steps = iter_compact_steps(tree)
    ids = {s.get("stepId") for s in steps if isinstance(s, dict)}
    assert ids == {"root", "a", "b", "c"}


def test_simplify_strategy_details_prefers_step_map_fields() -> None:
    details = {
        "recordClassName": "GeneRecordClasses.GeneRecordClass",
        "rootStepId": 123,
        "stepTree": {"stepId": "1"},
        "steps": {
            "1": {
                "displayName": "Display",
                "searchName": "search_q",
                "operator": "UNION",
                "searchConfig": {"parameters": {"k": "v"}},
            }
        },
    }
    compact = simplify_strategy_details(details)  # type: ignore[arg-type]
    assert compact["recordClassName"] == details["recordClassName"]
    assert compact["rootStepId"] == 123
    assert isinstance(compact["stepTree"], dict)
    assert compact["stepTree"]["searchName"] == "search_q"
    assert compact["stepTree"]["displayName"] == "Display"
    assert compact["stepTree"]["operator"] == "UNION"
    assert compact["stepTree"]["parameters"] == {"k": "v"}


def test_full_strategy_payload_includes_steps_and_tree() -> None:
    details = {
        "recordClassName": "x",
        "rootStepId": 1,
        "stepTree": {"stepId": "1"},
        "steps": {},
    }
    payload = full_strategy_payload(details)  # type: ignore[arg-type]
    assert payload["recordClassName"] == "x"
    assert payload["rootStepId"] == 1
    assert payload["stepTree"] == {"stepId": "1"}
    assert payload["steps"] == {}


def test_embedding_text_for_example_includes_search_name_and_params() -> None:
    compact = {
        "recordClassName": "GeneRecordClasses.GeneRecordClass",
        "stepTree": {
            "searchName": "search_q",
            "operator": "UNION",
            "parameters": {"p": "value"},
        },
    }
    text = embedding_text_for_example(name="N", description="D", compact=compact)  # type: ignore[arg-type]
    assert "N" in text
    assert "D" in text
    assert "search_q" in text
    assert "UNION" in text
    assert "p=" in text

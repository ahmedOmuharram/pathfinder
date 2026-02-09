from veupath_chatbot.ai.tools.query_validation import (
    record_type_query_error,
    search_query_error,
    tokenize_query,
)


def test_tokenize_query_extracts_keywords() -> None:
    assert tokenize_query("Vector salivary gland") == ["vector", "salivary", "gland"]
    assert tokenize_query("gene") == ["gene"]


def test_record_type_query_error_allows_blank() -> None:
    assert record_type_query_error("") is None


def test_record_type_query_error_rejects_one_word() -> None:
    err = record_type_query_error("gene")
    assert err is not None
    assert err["error"] == "query_too_vague"


def test_record_type_query_error_rejects_all_vague_tokens() -> None:
    err = record_type_query_error("gene transcript record")
    assert err is not None
    assert err["error"] == "query_too_vague"


def test_search_query_error_requires_non_empty() -> None:
    err = search_query_error(" ")
    assert err is not None
    assert err["error"] == "query_required"


def test_search_query_error_rejects_one_word() -> None:
    err = search_query_error("ortholog")
    assert err is not None
    assert err["error"] == "query_too_vague"


def test_search_query_error_allows_two_words() -> None:
    assert search_query_error("ortholog transform") is None

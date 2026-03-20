"""Tests for WDK transform functions (wdk_transform.py)."""

from veupath_chatbot.domain.parameters.specs import unwrap_search_data
from veupath_chatbot.integrations.vectorstore.ingest.wdk_transform import (
    _coerce_str,
    _preview_vocab,
    build_record_type_doc,
    build_search_doc,
)
from veupath_chatbot.integrations.vectorstore.qdrant_store import point_uuid


class TestCoerceStr:
    def test_string_value(self) -> None:
        assert _coerce_str("hello") == "hello"

    def test_none_returns_empty(self) -> None:
        assert _coerce_str(None) == ""

    def test_int_value(self) -> None:
        assert _coerce_str(42) == "42"

    def test_bool_value(self) -> None:
        assert _coerce_str(True) == "True"


class TestPreviewVocab:
    def test_none_vocab_returns_empty(self) -> None:
        values, truncated = _preview_vocab(None)
        assert values == []
        assert truncated is False

    def test_empty_list_returns_empty(self) -> None:
        values, truncated = _preview_vocab([])
        assert values == []
        assert truncated is False

    def test_flat_list_vocab(self) -> None:
        """List-of-lists vocab format: [[value, display], ...]"""
        vocab = [["val1", "Display 1"], ["val2", "Display 2"]]
        values, truncated = _preview_vocab(vocab)
        assert len(values) == 2
        assert truncated is False
        # Display values should appear
        assert "Display 1" in values
        assert "Display 2" in values

    def test_truncation_at_limit(self) -> None:
        vocab = [[f"val{i}", f"Display {i}"] for i in range(100)]
        values, truncated = _preview_vocab(vocab, limit=5)
        assert len(values) == 5
        assert truncated is True

    def test_deduplication(self) -> None:
        vocab = [["val1", "Same"], ["val2", "Same"]]
        values, _truncated = _preview_vocab(vocab)
        assert values.count("Same") == 1

    def test_tree_vocab(self) -> None:
        """Dict-based tree vocab format used by WDK."""
        vocab = {
            "data": {"display": "Root", "term": "root_term"},
            "children": [
                {"data": {"display": "Child A", "term": "a"}, "children": []},
                {"data": {"display": "Child B", "term": "b"}, "children": []},
            ],
        }
        values, truncated = _preview_vocab(vocab)
        assert len(values) == 3
        assert truncated is False

    def test_string_scalar_returns_empty(self) -> None:
        values, truncated = _preview_vocab("not-a-vocab")
        assert values == []
        assert truncated is False

    def test_skips_none_first_element(self) -> None:
        vocab = [[None, "display"]]
        values, _truncated = _preview_vocab(vocab)
        assert values == []


class TestUnwrapSearchData:
    def test_none_returns_none(self) -> None:
        assert unwrap_search_data(None) is None

    def test_dict_without_search_data_returns_self(self) -> None:
        d = {"searchName": "test", "displayName": "Test"}
        assert unwrap_search_data(d) == d

    def test_dict_with_search_data_returns_inner(self) -> None:
        inner = {"searchName": "inner_search"}
        d = {"searchData": inner, "otherField": "ignored"}
        assert unwrap_search_data(d) == inner

    def test_non_dict_search_data_returns_outer(self) -> None:
        d = {"searchData": "not-a-dict", "searchName": "outer"}
        assert unwrap_search_data(d) == d


class TestBuildRecordTypeDoc:
    def test_string_record_type(self) -> None:
        doc = build_record_type_doc("plasmodb", "transcript")
        assert doc is not None
        assert doc["id"] == point_uuid("plasmodb:transcript")
        assert "transcript" in doc["text"]
        payload = doc["payload"]
        assert payload["siteId"] == "plasmodb"
        assert payload["recordType"] == "transcript"
        assert payload["source"] == "wdk"

    def test_dict_record_type(self) -> None:
        rt = {
            "urlSegment": "gene",
            "displayName": "Genes",
            "description": "Gene records",
            "name": "GeneRecordClasses.GeneRecordClass",
        }
        doc = build_record_type_doc("toxodb", rt)
        assert doc is not None
        assert doc["id"] == point_uuid("toxodb:gene")
        payload = doc["payload"]
        assert payload["recordType"] == "gene"
        assert payload["displayName"] == "Genes"
        assert payload["description"] == "Gene records"
        assert payload["name"] == "GeneRecordClasses.GeneRecordClass"

    def test_empty_name_returns_none(self) -> None:
        rt = {"urlSegment": "", "name": ""}
        assert build_record_type_doc("site", rt) is None

    def test_non_dict_non_str_returns_none(self) -> None:
        assert build_record_type_doc("site", 42) is None
        assert build_record_type_doc("site", []) is None

    def test_text_includes_display_name_and_description(self) -> None:
        rt = {
            "urlSegment": "gene",
            "displayName": "Gene Records",
            "description": "All gene records in the database",
        }
        doc = build_record_type_doc("site", rt)
        assert doc is not None
        assert "Gene Records" in doc["text"]
        assert "All gene records in the database" in doc["text"]


class TestBuildSearchDoc:
    def _minimal_search(self) -> dict:
        return {
            "urlSegment": "GenesByText",
            "displayName": "Text Search",
            "description": "Search genes by text",
            "isInternal": False,
        }

    def test_basic_search_doc(self) -> None:
        s = self._minimal_search()
        doc = build_search_doc(
            site_id="plasmodb",
            rt_name="transcript",
            s=s,
            details_unwrapped={
                "displayName": "Text Search",
                "description": "Search genes by text",
            },
            details_error=None,
            base_url="https://plasmodb.org/plasmodb/service",
        )
        assert doc is not None
        assert doc["id"] == point_uuid("plasmodb:transcript:GenesByText")
        payload = doc["payload"]
        assert payload["siteId"] == "plasmodb"
        assert payload["recordType"] == "transcript"
        assert payload["searchName"] == "GenesByText"
        assert payload["displayName"] == "Text Search"
        assert "sourceUrl" in payload
        assert "sourceHash" in payload
        assert isinstance(payload["ingestedAt"], int)

    def test_internal_search_returns_none(self) -> None:
        s = {"urlSegment": "internal_search", "isInternal": True}
        doc = build_search_doc("site", "rt", s, {}, None, "http://example.com")
        assert doc is None

    def test_empty_search_name_returns_none(self) -> None:
        s = {"urlSegment": "", "name": ""}
        doc = build_search_doc("site", "rt", s, {}, None, "http://example.com")
        assert doc is None

    def test_non_dict_returns_none(self) -> None:
        doc = build_search_doc("site", "rt", "not-a-dict", {}, None, "http://x.com")
        assert doc is None

    def test_details_error_added_to_payload(self) -> None:
        s = self._minimal_search()
        doc = build_search_doc(
            "site", "rt", s, {}, "connection error", "http://example.com"
        )
        assert doc is not None
        assert doc["payload"]["detailsError"] == "connection error"

    def test_text_field_includes_search_metadata(self) -> None:
        s = self._minimal_search()
        doc = build_search_doc(
            "site",
            "transcript",
            s,
            {"displayName": "Text Search", "summary": "Find genes"},
            None,
            "http://example.com",
        )
        assert doc is not None
        text = doc["text"]
        assert "Text Search" in text
        assert "GenesByText" in text
        assert "transcript" in text
        assert "Find genes" in text

    def test_param_specs_are_extracted(self) -> None:
        s = self._minimal_search()
        details = {
            "displayName": "Text Search",
            "parameters": [
                {
                    "name": "text_expression",
                    "displayName": "Text Term",
                    "type": "string",
                    "help": "Enter search text",
                    "isRequired": True,
                }
            ],
        }
        doc = build_search_doc("site", "rt", s, details, None, "http://example.com")
        assert doc is not None
        params = doc["payload"]["paramSpecs"]
        assert isinstance(params, list)
        assert len(params) == 1
        assert params[0]["name"] == "text_expression"
        assert params[0]["displayName"] == "Text Term"
        assert params[0]["isRequired"] is True

    def test_source_url_format(self) -> None:
        s = self._minimal_search()
        doc = build_search_doc(
            "plasmodb",
            "transcript",
            s,
            {},
            None,
            "https://plasmodb.org/plasmodb/service",
        )
        assert doc is not None
        expected = "https://plasmodb.org/plasmodb/service/record-types/transcript/searches/GenesByText"
        assert doc["payload"]["sourceUrl"] == expected

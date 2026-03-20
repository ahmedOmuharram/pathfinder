"""Edge case and regression tests for vectorstore modules.

Covers:
  - QdrantStore helper functions with unusual inputs
  - QdrantStore._get_with_client dense vector handling
  - Bootstrap _known_embedding_dims gap analysis
  - Ingest utils edge cases
  - Public strategies helpers edge cases
  - Embeddings _chunks edge cases
  - WDK transform with malformed/edge-case data
  - Collection name safety
"""

import json
import re
import uuid
from dataclasses import dataclass
from unittest.mock import AsyncMock

import pytest

from veupath_chatbot.integrations.embeddings.openai_embeddings import _chunks
from veupath_chatbot.integrations.vectorstore.bootstrap import _known_embedding_dims
from veupath_chatbot.integrations.vectorstore.collections import (
    EXAMPLE_PLANS_V1,
    WDK_DEPENDENT_VOCAB_CACHE_V1,
    WDK_RECORD_TYPES_V1,
    WDK_SEARCHES_V1,
)
from veupath_chatbot.integrations.vectorstore.ingest.public_strategies_helpers import (
    backoff_delay_seconds,
    embedding_text_for_example,
    iter_compact_steps,
    simplify_strategy_details,
    truncate,
)
from veupath_chatbot.integrations.vectorstore.ingest.utils import parse_sites
from veupath_chatbot.integrations.vectorstore.ingest.wdk_transform import (
    _preview_vocab,
    build_record_type_doc,
    build_search_doc,
)
from veupath_chatbot.integrations.vectorstore.qdrant_store import (
    QdrantStore,
    context_hash,
    point_uuid,
    sha256_hex,
    stable_json_dumps,
)

# ===========================================================================
# QdrantStore pure helpers
# ===========================================================================


class TestStableJsonDumpsEdgeCases:
    """Edge cases for stable_json_dumps."""

    def test_unicode_characters_preserved(self) -> None:
        result = stable_json_dumps({"name": "Plasmodium falciparum"})
        assert "Plasmodium falciparum" in result

    def test_special_json_chars_escaped(self) -> None:
        result = stable_json_dumps({"key": 'value with "quotes"'})
        parsed = json.loads(result)
        assert parsed["key"] == 'value with "quotes"'

    def test_deeply_nested(self) -> None:
        deep = {"a": {"b": {"c": {"d": "e"}}}}
        result = stable_json_dumps(deep)
        parsed = json.loads(result)
        assert parsed["a"]["b"]["c"]["d"] == "e"

    def test_mixed_types(self) -> None:
        result = stable_json_dumps(
            {"s": "str", "i": 42, "f": 3.14, "b": True, "n": None}
        )
        parsed = json.loads(result)
        assert parsed["s"] == "str"
        assert parsed["i"] == 42
        assert parsed["b"] is True
        assert parsed["n"] is None

    def test_large_list(self) -> None:
        """Large lists should not cause issues."""
        big_list = list(range(10000))
        result = stable_json_dumps(big_list)
        parsed = json.loads(result)
        assert len(parsed) == 10000


class TestSha256HexEdgeCases:
    def test_unicode_input(self) -> None:
        result = sha256_hex("cafe\u0301")
        assert len(result) == 64

    def test_very_long_input(self) -> None:
        result = sha256_hex("a" * 1_000_000)
        assert len(result) == 64


class TestPointUuidEdgeCases:
    def test_empty_key(self) -> None:
        result = point_uuid("")
        # Should still produce a valid UUID
        uuid.UUID(result)

    def test_special_characters(self) -> None:
        result = point_uuid("key with spaces/slashes:colons")
        uuid.UUID(result)

    def test_unicode_key(self) -> None:
        result = point_uuid("key\u2019with\u2013unicode")
        uuid.UUID(result)

    def test_very_long_key(self) -> None:
        result = point_uuid("x" * 100_000)
        uuid.UUID(result)


class TestContextHashEdgeCases:
    def test_nested_values(self) -> None:
        ctx = {"param": {"nested": [1, 2, 3]}}
        result = context_hash(ctx)
        assert len(result) == 64

    def test_null_values(self) -> None:
        ctx = {"param": None}
        result = context_hash(ctx)
        assert len(result) == 64


# ===========================================================================
# QdrantStore._get_with_client dense vector handling
# ===========================================================================


@dataclass
class _FakePoint:
    """Minimal stand-in for a qdrant_client Record/ScoredPoint."""

    id: str
    payload: dict[str, object] | None
    vector: list[float] | None


class TestGetWithClientDenseVector:
    """Verify _get_with_client returns correct JSON for dense vectors."""

    async def _call(
        self, vector: list[float] | None, payload: dict[str, object] | None = None
    ) -> dict[str, object] | None:
        store = QdrantStore(url="http://localhost:6333")
        fake_client = AsyncMock()
        fake_client.retrieve = AsyncMock(
            return_value=[_FakePoint(id="pt-1", payload=payload or {}, vector=vector)]
        )
        return await store._get_with_client(fake_client, "test_col", "pt-1")

    @pytest.mark.asyncio
    async def test_dense_vector_returned_as_float_list(self) -> None:
        result = await self._call([0.1, 0.2, 0.3])
        assert result is not None
        assert result["id"] == "pt-1"
        assert result["vector"] == [0.1, 0.2, 0.3]
        assert all(isinstance(v, float) for v in result["vector"])

    @pytest.mark.asyncio
    async def test_none_vector_returned_as_none(self) -> None:
        result = await self._call(None)
        assert result is not None
        assert result["vector"] is None

    @pytest.mark.asyncio
    async def test_empty_vector_returned_as_empty_list(self) -> None:
        result = await self._call([])
        assert result is not None
        assert result["vector"] == []

    @pytest.mark.asyncio
    async def test_payload_preserved(self) -> None:
        result = await self._call([1.0], payload={"site": "PlasmoDB"})
        assert result is not None
        assert result["payload"] == {"site": "PlasmoDB"}

    @pytest.mark.asyncio
    async def test_null_payload_becomes_empty_dict(self) -> None:
        result = await self._call([1.0], payload=None)
        assert result is not None
        assert result["payload"] == {}

    @pytest.mark.asyncio
    async def test_empty_result_returns_none(self) -> None:
        store = QdrantStore(url="http://localhost:6333")
        fake_client = AsyncMock()
        fake_client.retrieve = AsyncMock(return_value=[])
        result = await store._get_with_client(fake_client, "test_col", "missing")
        assert result is None

    @pytest.mark.asyncio
    async def test_qdrant_error_returns_none(self) -> None:
        store = QdrantStore(url="http://localhost:6333")
        fake_client = AsyncMock()
        fake_client.retrieve = AsyncMock(side_effect=RuntimeError("connection refused"))
        result = await store._get_with_client(fake_client, "test_col", "pt-1")
        assert result is None

    @pytest.mark.asyncio
    async def test_integer_values_coerced_to_float(self) -> None:
        result = await self._call([1, 2, 3])
        assert result is not None
        assert result["vector"] == [1.0, 2.0, 3.0]
        assert all(isinstance(v, float) for v in result["vector"])


# ===========================================================================
# Bootstrap
# ===========================================================================


class TestKnownEmbeddingDimsEdgeCases:
    def test_case_sensitive(self) -> None:
        """Model names are case-sensitive."""
        assert _known_embedding_dims("Text-Embedding-3-Small") is None

    def test_partial_match_returns_none(self) -> None:
        assert _known_embedding_dims("text-embedding-3") is None

    def test_ada_not_supported(self) -> None:
        assert _known_embedding_dims("text-embedding-ada-002") is None


# ===========================================================================
# Ingest utilities
# ===========================================================================


class TestParseSitesEdgeCases:
    def test_only_commas(self) -> None:
        result = parse_sites(",,,")
        # All segments are empty after split+strip
        assert result == [] or result is None

    def test_whitespace_only_site(self) -> None:
        result = parse_sites("  ,  ,  ")
        # All segments are empty after strip
        assert result is None or result == []


# ===========================================================================
# Public strategies helpers
# ===========================================================================


class TestTruncateRobustness:
    """Verify truncation behavior at boundary conditions."""

    def test_suffix_is_12_chars(self) -> None:
        """The truncation suffix is 12 chars: '...(truncated)'"""
        suffix = "\u2026(truncated)"
        assert len(suffix) == 12

    def test_max_chars_less_than_suffix_len(self) -> None:
        """When max_chars < suffix length, result is just the suffix."""
        result = truncate("hello world!", max_chars=5)
        # Slice yields empty string since max_chars < suffix length
        assert result == "\u2026(truncated)"

    def test_exact_boundary(self) -> None:
        s = "a" * 100
        result = truncate(s, max_chars=100)
        assert result == s  # no truncation needed

    def test_one_over(self) -> None:
        s = "a" * 101
        result = truncate(s, max_chars=100)
        assert result.endswith("\u2026(truncated)")
        # The body is s[:max(0, 100-20)] = s[:80]
        assert len(result) == 80 + 12  # 92 chars

    def test_negative_max_chars(self) -> None:
        """Negative max_chars: s[:max(0, -1-20)] = s[:0] + suffix."""
        result = truncate("hello", max_chars=-1)
        assert result == "\u2026(truncated)"


class TestBackoffDelayEdgeCases:
    def test_attempt_zero(self) -> None:
        # 2^(0-1) = 0.5, int(min(8, 0.5)) = 0
        assert backoff_delay_seconds(0) == 0

    def test_large_attempt(self) -> None:
        assert backoff_delay_seconds(100) == 8

    def test_negative_attempt(self) -> None:
        # 2^(-2) = 0.25 => int(min(8, 0.25)) = 0
        assert backoff_delay_seconds(-1) == 0


class TestIterCompactStepsEdgeCases:
    def test_empty_dict(self) -> None:
        steps = iter_compact_steps({})
        assert len(steps) == 1  # The root node itself

    def test_non_dict_children_ignored(self) -> None:
        tree = {
            "stepId": "root",
            "primaryInput": "not-a-dict",
            "secondaryInput": 42,
        }
        steps = iter_compact_steps(tree)
        assert len(steps) == 1

    def test_diamond_shape(self) -> None:
        """Each child is visited independently (even if stepId repeats)."""
        tree = {
            "stepId": "root",
            "primaryInput": {"stepId": "shared"},
            "secondaryInput": {"stepId": "shared"},
        }
        steps = iter_compact_steps(tree)
        # Both children visited even though stepId is the same
        assert len(steps) == 3


class TestSimplifyStrategyDetailsEdgeCases:
    def test_missing_step_tree(self) -> None:
        """When stepTree is absent, the result should be None."""
        details = {"recordClassName": "Gene", "rootStepId": 1}
        compact = simplify_strategy_details(details)
        assert compact["stepTree"] is None

    def test_steps_is_not_dict(self) -> None:
        details = {
            "recordClassName": "Gene",
            "rootStepId": 1,
            "stepTree": {"stepId": "1"},
            "steps": "not-a-dict",
        }
        compact = simplify_strategy_details(details)
        # steps.get("1") with non-dict steps => None
        assert compact["stepTree"]["searchName"] is None

    def test_step_with_no_operator_key(self) -> None:
        """When no parameter key contains 'operator', operator should be None."""
        details = {
            "recordClassName": "Gene",
            "rootStepId": 1,
            "stepTree": {"stepId": "1"},
            "steps": {
                "1": {
                    "searchName": "test",
                    "searchConfig": {"parameters": {"key": "value"}},
                }
            },
        }
        compact = simplify_strategy_details(details)
        assert compact["stepTree"]["operator"] is None


class TestEmbeddingTextForExampleEdgeCases:
    def test_empty_name_and_description(self) -> None:
        text = embedding_text_for_example(name="", description="", compact={})
        # Should still produce some text (at least the recordClassName line)
        assert isinstance(text, str)

    def test_step_with_no_parameters(self) -> None:
        compact = {
            "stepTree": {"searchName": "S1"},
        }
        text = embedding_text_for_example(name="N", description="D", compact=compact)
        assert "S1" in text

    def test_many_params_limited_to_20(self) -> None:
        """Only first 20 parameters rendered per step."""
        params = {f"param_{i}": f"value_{i}" for i in range(30)}
        compact = {
            "stepTree": {"searchName": "S1", "parameters": params},
        }
        text = embedding_text_for_example(name="N", description="D", compact=compact)
        # At most 20 params should appear
        assert text.count("param_") <= 20


# ===========================================================================
# WDK transform edge cases
# ===========================================================================


class TestBuildRecordTypeDocEdgeCases:
    def test_none_input(self) -> None:
        assert build_record_type_doc("site", None) is None

    def test_list_input(self) -> None:
        assert build_record_type_doc("site", []) is None

    def test_float_input(self) -> None:
        assert build_record_type_doc("site", 3.14) is None

    def test_missing_display_name_falls_back_to_name(self) -> None:
        rt = {"urlSegment": "gene"}
        doc = build_record_type_doc("site", rt)
        assert doc is not None
        assert doc["payload"]["displayName"] == "gene"

    def test_empty_description(self) -> None:
        rt = {"urlSegment": "gene", "description": ""}
        doc = build_record_type_doc("site", rt)
        assert doc is not None
        assert doc["payload"]["description"] == ""


class TestBuildSearchDocEdgeCases:
    def test_missing_display_name_uses_url_segment(self) -> None:
        s = {"urlSegment": "GenesByText"}
        doc = build_search_doc("site", "rt", s, {}, None, "http://example.com")
        assert doc is not None
        assert doc["payload"]["displayName"] == "GenesByText"

    def test_source_hash_changes_with_payload(self) -> None:
        s = {"urlSegment": "S1"}
        doc1 = build_search_doc(
            "site", "rt", s, {"displayName": "A"}, None, "http://example.com"
        )
        doc2 = build_search_doc(
            "site", "rt", s, {"displayName": "B"}, None, "http://example.com"
        )
        assert doc1 is not None
        assert doc2 is not None
        assert doc1["payload"]["sourceHash"] != doc2["payload"]["sourceHash"]

    def test_all_wdk_fields_populated(self) -> None:
        """Verify that the comprehensive WDK fields are present in payload."""
        s = {"urlSegment": "S1"}
        details = {
            "displayName": "Search One",
            "fullName": "org.S1",
            "outputRecordClassName": "GeneClass",
            "paramNames": ["p1"],
            "groups": [{"name": "g1"}],
            "filters": [],
            "defaultAttributes": ["attr1"],
            "defaultSorting": [{"attributeName": "attr1"}],
            "isAnalyzable": True,
            "isCacheable": True,
            "isBeta": False,
            "queryName": "GenesByText",
            "newBuild": "68",
        }
        doc = build_search_doc("site", "rt", s, details, None, "http://example.com")
        assert doc is not None
        p = doc["payload"]
        assert p["fullName"] == "org.S1"
        assert p["outputRecordClassName"] == "GeneClass"
        assert p["paramNames"] == ["p1"]
        assert p["isAnalyzable"] is True

    def test_details_error_included(self) -> None:
        s = {"urlSegment": "S1"}
        doc = build_search_doc("site", "rt", s, {}, "timeout", "http://example.com")
        assert doc is not None
        assert doc["payload"]["detailsError"] == "timeout"


class TestPreviewVocabEdgeCases:
    def test_dict_vocab_deep_tree(self) -> None:
        """Deep tree vocab should be flattened."""
        vocab = {
            "data": {"display": "Root", "term": "root"},
            "children": [
                {
                    "data": {"display": "L1", "term": "l1"},
                    "children": [
                        {"data": {"display": "L2", "term": "l2"}, "children": []},
                    ],
                },
            ],
        }
        values, truncated = _preview_vocab(vocab)
        assert len(values) == 3
        assert "Root" in values
        assert "L1" in values
        assert "L2" in values
        assert truncated is False

    def test_empty_dict_vocab(self) -> None:
        values, truncated = _preview_vocab({})
        assert values == []
        assert truncated is False

    def test_mixed_list_vocab(self) -> None:
        """List vocab with mixed types."""
        vocab = [
            ["val1", "Display 1"],
            {"display": "Display 2", "value": "val2"},
            "plain_string",
        ]
        values, _truncated = _preview_vocab(vocab)
        # Should handle all three formats
        assert len(values) >= 2

    def test_limit_zero(self) -> None:
        """limit=0 returns empty list and marks as truncated (nothing fits)."""
        vocab = [["val1", "Display 1"]]
        values, truncated = _preview_vocab(vocab, limit=0)
        assert values == []
        assert truncated is True


# ===========================================================================
# Collection name safety
# ===========================================================================


class TestCollectionNameSafety:
    """Verify collection names meet Qdrant requirements."""

    def test_no_spaces(self) -> None:
        for name in (
            WDK_RECORD_TYPES_V1,
            WDK_SEARCHES_V1,
            WDK_DEPENDENT_VOCAB_CACHE_V1,
            EXAMPLE_PLANS_V1,
        ):
            assert " " not in name

    def test_no_special_chars(self) -> None:
        for name in (
            WDK_RECORD_TYPES_V1,
            WDK_SEARCHES_V1,
            WDK_DEPENDENT_VOCAB_CACHE_V1,
            EXAMPLE_PLANS_V1,
        ):
            assert re.fullmatch(r"[a-z0-9_]+", name), f"Unsafe collection name: {name}"

    def test_reasonable_length(self) -> None:
        for name in (
            WDK_RECORD_TYPES_V1,
            WDK_SEARCHES_V1,
            WDK_DEPENDENT_VOCAB_CACHE_V1,
            EXAMPLE_PLANS_V1,
        ):
            assert len(name) < 100


# ===========================================================================
# Embeddings _chunks edge cases
# ===========================================================================


class TestChunksEdgeCases:
    def test_single_item(self) -> None:
        result = list(_chunks(["a"], size=1))
        assert result == [["a"]]

    def test_chunk_larger_than_list(self) -> None:
        result = list(_chunks(["a"], size=100))
        assert result == [["a"]]

    def test_preserves_order(self) -> None:
        items = [str(i) for i in range(20)]
        result = list(_chunks(items, size=7))
        flat = [x for chunk in result for x in chunk]
        assert flat == items

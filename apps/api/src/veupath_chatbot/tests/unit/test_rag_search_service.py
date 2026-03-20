"""Tests for services.catalog.rag_search — the shared RAG search service.

All external calls (embeddings, Qdrant, settings) are mocked so tests run
without network or infrastructure.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from veupath_chatbot.services.catalog.rag_search import (
    RagSearchService,
    _extract_payload,
    _extract_score,
    _threshold_and_limit,
)

# ── fixtures ─────────────────────────────────────────────────────────


def _fake_settings(rag_enabled: bool = True) -> MagicMock:
    s = MagicMock()
    s.rag_enabled = rag_enabled
    s.embeddings_model = "text-embedding-3-small"
    return s


def _make_hit(
    *,
    score: float,
    payload: dict[str, object] | None = None,
    point_id: str = "abc",
) -> dict[str, object]:
    return {"id": point_id, "score": score, "payload": payload or {}}


def _make_service(store: AsyncMock | None = None) -> RagSearchService:
    return RagSearchService(site_id="plasmodb", store=store or AsyncMock())


# ── _extract_score ───────────────────────────────────────────────────


class TestExtractScore:
    def test_float(self):
        assert _extract_score({"score": 0.85}) == 0.85

    def test_int(self):
        assert _extract_score({"score": 1}) == 1.0

    def test_string(self):
        assert _extract_score({"score": "0.5"}) == 0.5

    def test_missing(self):
        assert _extract_score({}) == 0.0

    def test_none(self):
        assert _extract_score({"score": None}) == 0.0

    def test_non_numeric(self):
        assert _extract_score({"score": [1, 2]}) == 0.0


# ── _extract_payload ────────────────────────────────────────────────


class TestExtractPayload:
    def test_dict_payload(self):
        assert _extract_payload({"payload": {"a": 1}}) == {"a": 1}

    def test_missing(self):
        assert _extract_payload({}) is None

    def test_non_dict(self):
        assert _extract_payload({"payload": "not a dict"}) is None


# ── _threshold_and_limit ────────────────────────────────────────────


class TestThresholdAndLimit:
    def test_filters_below_threshold(self):
        hits = [
            _make_hit(score=0.8, payload={"x": 1}),
            _make_hit(score=0.2, payload={"x": 2}),
        ]
        result = _threshold_and_limit(hits, min_score=0.5, limit=10)
        assert len(result) == 1
        assert result[0]["x"] == 1

    def test_limits_output(self):
        hits = [_make_hit(score=0.9, payload={"i": i}) for i in range(10)]
        result = _threshold_and_limit(hits, min_score=0.0, limit=3)
        assert len(result) == 3

    def test_prunes_keys(self):
        hits = [_make_hit(score=0.9, payload={"keep": 1, "drop_me": 2, "also_drop": 3})]
        result = _threshold_and_limit(
            hits, min_score=0.0, limit=10, prune_keys=("drop_me", "also_drop")
        )
        assert len(result) == 1
        assert "keep" in result[0]
        assert "drop_me" not in result[0]
        assert "also_drop" not in result[0]

    def test_score_added_to_output(self):
        hits = [_make_hit(score=0.75, payload={"a": 1})]
        result = _threshold_and_limit(hits, min_score=0.0, limit=10)
        assert result[0]["score"] == 0.75

    def test_skips_non_dict_hits(self):
        hits = ["not_a_dict", _make_hit(score=0.9, payload={"ok": True})]
        result = _threshold_and_limit(hits, min_score=0.0, limit=10)
        assert len(result) == 1

    def test_skips_hits_without_payload(self):
        hits = [{"score": 0.9}]  # no payload key
        result = _threshold_and_limit(hits, min_score=0.0, limit=10)
        assert len(result) == 0

    def test_empty_hits(self):
        assert _threshold_and_limit([], min_score=0.0, limit=10) == []


# ── RagSearchService.search_record_types ────────────────────────────


class TestSearchRecordTypes:
    @pytest.mark.asyncio
    async def test_returns_empty_when_rag_disabled(self):
        with patch(
            "veupath_chatbot.services.catalog.rag_search.get_settings",
            return_value=_fake_settings(rag_enabled=False),
        ):
            svc = _make_service()
            result = await svc.search_record_types(query="gene expression")
            assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_for_empty_query(self):
        with (
            patch(
                "veupath_chatbot.services.catalog.rag_search.get_settings",
                return_value=_fake_settings(),
            ),
            patch(
                "veupath_chatbot.services.catalog.rag_search.ensure_rag_collections",
                new_callable=AsyncMock,
            ),
        ):
            svc = _make_service()
            result = await svc.search_record_types(query="")
            assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_for_none_query(self):
        with (
            patch(
                "veupath_chatbot.services.catalog.rag_search.get_settings",
                return_value=_fake_settings(),
            ),
            patch(
                "veupath_chatbot.services.catalog.rag_search.ensure_rag_collections",
                new_callable=AsyncMock,
            ),
        ):
            svc = _make_service()
            result = await svc.search_record_types(query=None)
            assert result == []

    @pytest.mark.asyncio
    async def test_embeds_and_searches(self):
        store = AsyncMock()
        store.search = AsyncMock(
            return_value=[
                _make_hit(
                    score=0.9, payload={"urlSegment": "gene", "siteId": "plasmodb"}
                ),
            ]
        )
        with (
            patch(
                "veupath_chatbot.services.catalog.rag_search.get_settings",
                return_value=_fake_settings(),
            ),
            patch(
                "veupath_chatbot.services.catalog.rag_search.ensure_rag_collections",
                new_callable=AsyncMock,
            ),
            patch(
                "veupath_chatbot.services.catalog.rag_search.embed_one",
                new_callable=AsyncMock,
                return_value=[0.1, 0.2],
            ),
        ):
            svc = RagSearchService(site_id="plasmodb", store=store)
            result = await svc.search_record_types(query="gene expression", limit=5)
            assert len(result) == 1
            assert result[0]["urlSegment"] == "gene"
            assert result[0]["score"] == 0.9
            store.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_prunes_heavy_fields(self):
        store = AsyncMock()
        store.search = AsyncMock(
            return_value=[
                _make_hit(
                    score=0.9,
                    payload={
                        "urlSegment": "gene",
                        "formats": ["big_data"],
                        "attributes": ["many_attrs"],
                        "tables": ["big_tables"],
                    },
                ),
            ]
        )
        with (
            patch(
                "veupath_chatbot.services.catalog.rag_search.get_settings",
                return_value=_fake_settings(),
            ),
            patch(
                "veupath_chatbot.services.catalog.rag_search.ensure_rag_collections",
                new_callable=AsyncMock,
            ),
            patch(
                "veupath_chatbot.services.catalog.rag_search.embed_one",
                new_callable=AsyncMock,
                return_value=[0.1],
            ),
        ):
            svc = RagSearchService(site_id="plasmodb", store=store)
            result = await svc.search_record_types(query="gene expression")
            assert "formats" not in result[0]
            assert "attributes" not in result[0]
            assert "tables" not in result[0]


# ── RagSearchService.get_record_type_details ────────────────────────


class TestGetRecordTypeDetails:
    @pytest.mark.asyncio
    async def test_returns_none_when_rag_disabled(self):
        with patch(
            "veupath_chatbot.services.catalog.rag_search.get_settings",
            return_value=_fake_settings(rag_enabled=False),
        ):
            svc = _make_service()
            result = await svc.get_record_type_details("gene")
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_empty_id(self):
        with patch(
            "veupath_chatbot.services.catalog.rag_search.get_settings",
            return_value=_fake_settings(),
        ):
            svc = _make_service()
            result = await svc.get_record_type_details("")
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_payload_on_hit(self):
        store = AsyncMock()
        store.get = AsyncMock(
            return_value={"payload": {"urlSegment": "gene", "displayName": "Gene"}}
        )
        with patch(
            "veupath_chatbot.services.catalog.rag_search.get_settings",
            return_value=_fake_settings(),
        ):
            svc = RagSearchService(site_id="plasmodb", store=store)
            result = await svc.get_record_type_details("gene")
            assert result == {"urlSegment": "gene", "displayName": "Gene"}

    @pytest.mark.asyncio
    async def test_returns_none_on_miss(self):
        store = AsyncMock()
        store.get = AsyncMock(return_value=None)
        with patch(
            "veupath_chatbot.services.catalog.rag_search.get_settings",
            return_value=_fake_settings(),
        ):
            svc = RagSearchService(site_id="plasmodb", store=store)
            result = await svc.get_record_type_details("nonexistent")
            assert result is None


# ── RagSearchService.search_for_searches ────────────────────────────


class TestSearchForSearches:
    @pytest.mark.asyncio
    async def test_returns_empty_when_rag_disabled(self):
        with patch(
            "veupath_chatbot.services.catalog.rag_search.get_settings",
            return_value=_fake_settings(rag_enabled=False),
        ):
            svc = _make_service()
            result = await svc.search_for_searches(query="kinase")
            assert result == []

    @pytest.mark.asyncio
    async def test_prunes_heavy_fields(self):
        store = AsyncMock()
        store.search = AsyncMock(
            return_value=[
                _make_hit(
                    score=0.9,
                    payload={
                        "name": "GenesByGoTerm",
                        "score": "internal_score",
                        "format": "json",
                        "dynamicAttributes": ["big"],
                        "paramSpecs": ["big_specs"],
                    },
                ),
            ]
        )
        with (
            patch(
                "veupath_chatbot.services.catalog.rag_search.get_settings",
                return_value=_fake_settings(),
            ),
            patch(
                "veupath_chatbot.services.catalog.rag_search.ensure_rag_collections",
                new_callable=AsyncMock,
            ),
            patch(
                "veupath_chatbot.services.catalog.rag_search.embed_one",
                new_callable=AsyncMock,
                return_value=[0.1],
            ),
        ):
            svc = RagSearchService(site_id="plasmodb", store=store)
            result = await svc.search_for_searches(query="go term genes")
            assert len(result) == 1
            assert "format" not in result[0]
            assert "dynamicAttributes" not in result[0]
            assert "paramSpecs" not in result[0]
            # "score" key from payload is pruned; the outer score is from the hit
            assert result[0]["score"] == 0.9

    @pytest.mark.asyncio
    async def test_filters_by_record_type(self):
        store = AsyncMock()
        store.search = AsyncMock(return_value=[])
        with (
            patch(
                "veupath_chatbot.services.catalog.rag_search.get_settings",
                return_value=_fake_settings(),
            ),
            patch(
                "veupath_chatbot.services.catalog.rag_search.ensure_rag_collections",
                new_callable=AsyncMock,
            ),
            patch(
                "veupath_chatbot.services.catalog.rag_search.embed_one",
                new_callable=AsyncMock,
                return_value=[0.1],
            ),
        ):
            svc = RagSearchService(site_id="plasmodb", store=store)
            await svc.search_for_searches(query="kinase genes", record_type="gene")
            call_kwargs = store.search.call_args.kwargs
            must = call_kwargs["must"]
            assert len(must) == 2
            assert must[1] == {"key": "recordType", "value": "gene"}


# ── RagSearchService.get_search_metadata ────────────────────────────


class TestGetSearchMetadata:
    @pytest.mark.asyncio
    async def test_returns_none_when_rag_disabled(self):
        with patch(
            "veupath_chatbot.services.catalog.rag_search.get_settings",
            return_value=_fake_settings(rag_enabled=False),
        ):
            svc = _make_service()
            result = await svc.get_search_metadata("gene", "GenesByGoTerm")
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_payload_on_hit(self):
        store = AsyncMock()
        store.get = AsyncMock(return_value={"payload": {"name": "GenesByGoTerm"}})
        with patch(
            "veupath_chatbot.services.catalog.rag_search.get_settings",
            return_value=_fake_settings(),
        ):
            svc = RagSearchService(site_id="plasmodb", store=store)
            result = await svc.get_search_metadata("gene", "GenesByGoTerm")
            assert result == {"name": "GenesByGoTerm"}


# ── RagSearchService.get_dependent_vocab ────────────────────────────


class TestGetDependentVocab:
    @pytest.mark.asyncio
    async def test_returns_error_when_rag_disabled(self):
        with patch(
            "veupath_chatbot.services.catalog.rag_search.get_settings",
            return_value=_fake_settings(rag_enabled=False),
        ):
            svc = _make_service()
            result = await svc.get_dependent_vocab("gene", "GenesByGoTerm", "organism")
            assert result == {"error": "rag_disabled"}

    @pytest.mark.asyncio
    async def test_delegates_to_authoritative_cached(self):
        expected = {"cache": "hit", "wdkResponse": {"vocab": ["a", "b"]}}
        with (
            patch(
                "veupath_chatbot.services.catalog.rag_search.get_settings",
                return_value=_fake_settings(),
            ),
            patch(
                "veupath_chatbot.services.catalog.rag_search.get_dependent_vocab_authoritative_cached",
                new_callable=AsyncMock,
                return_value=expected,
            ) as mock_cached,
        ):
            svc = _make_service()
            result = await svc.get_dependent_vocab(
                "gene", "GenesByGoTerm", "organism", {"organism": "pfal"}
            )
            assert result == expected
            mock_cached.assert_called_once()


# ── RagSearchService.search_example_plans ───────────────────────────


class TestSearchExamplePlans:
    @pytest.mark.asyncio
    async def test_returns_empty_when_rag_disabled(self):
        with patch(
            "veupath_chatbot.services.catalog.rag_search.get_settings",
            return_value=_fake_settings(rag_enabled=False),
        ):
            svc = _make_service()
            result = await svc.search_example_plans(query="malaria")
            assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_for_empty_query(self):
        with (
            patch(
                "veupath_chatbot.services.catalog.rag_search.get_settings",
                return_value=_fake_settings(),
            ),
            patch(
                "veupath_chatbot.services.catalog.rag_search.ensure_rag_collections",
                new_callable=AsyncMock,
            ),
        ):
            svc = _make_service()
            result = await svc.search_example_plans(query="")
            assert result == []

    @pytest.mark.asyncio
    async def test_formats_plan_results(self):
        store = AsyncMock()
        store.search = AsyncMock(
            return_value=[
                {
                    "id": "p1",
                    "score": 0.88,
                    "payload": {
                        "sourceSignature": "sig1",
                        "sourceStrategyId": 42,
                        "sourceName": "My Plan",
                        "sourceDescription": "A test plan",
                        "generatedName": "Gen Plan",
                        "generatedDescription": "Generated desc",
                        "recordClassName": "gene",
                        "rootStepId": 1,
                        "strategyCompact": {"steps": []},
                        "strategyFull": {"steps": [{"id": 1}]},
                    },
                },
            ]
        )
        with (
            patch(
                "veupath_chatbot.services.catalog.rag_search.get_settings",
                return_value=_fake_settings(),
            ),
            patch(
                "veupath_chatbot.services.catalog.rag_search.ensure_rag_collections",
                new_callable=AsyncMock,
            ),
            patch(
                "veupath_chatbot.services.catalog.rag_search.embed_one",
                new_callable=AsyncMock,
                return_value=[0.1],
            ),
        ):
            svc = RagSearchService(site_id="plasmodb", store=store)
            result = await svc.search_example_plans(query="malaria liver stage")
            assert len(result) == 1
            plan = result[0]
            assert plan["score"] == 0.88
            assert plan["sourceName"] == "My Plan"
            assert plan["strategyCompact"] == {"steps": []}
            assert plan["strategyFull"] == {"steps": [{"id": 1}]}


# ── RagSearchService.get_search_details ─────────────────────────────


class TestGetSearchDetails:
    @pytest.mark.asyncio
    async def test_delegates_to_discovery_service(self):
        expected = {"searchData": {"parameters": []}}
        mock_discovery = MagicMock()
        mock_discovery.get_search_details = AsyncMock(return_value=expected)
        with patch(
            "veupath_chatbot.services.catalog.rag_search.get_discovery_service",
            return_value=mock_discovery,
        ):
            svc = _make_service()
            result = await svc.get_search_details("gene", "GenesByGoTerm")
            assert result == expected
            mock_discovery.get_search_details.assert_called_once_with(
                "plasmodb",
                "gene",
                "GenesByGoTerm",
                expand_params=True,
            )

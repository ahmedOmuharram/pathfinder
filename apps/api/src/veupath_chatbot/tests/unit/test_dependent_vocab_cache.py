"""Tests for dependent_vocab_cache.py -- pure-logic and mocked-async paths.

Covers:
  - Cache key construction (deterministic hashing, ordering invariance)
  - Cache hit path returns payload from store
  - Cache miss path calls WDK and upserts
  - Portal fallback on WDK error for non-veupathdb site
  - Re-raise on WDK error when already veupathdb
  - ensure_dependent_vocab_collection called on every invocation (perf bug documented)
"""

from contextlib import contextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from veupath_chatbot.domain.search import SearchContext
from veupath_chatbot.integrations.vectorstore.bootstrap import _KNOWN_DIMS
from veupath_chatbot.integrations.vectorstore.dependent_vocab_cache import (
    ensure_dependent_vocab_collection,
    get_dependent_vocab_authoritative_cached,
)
from veupath_chatbot.integrations.vectorstore.qdrant_store import (
    context_hash,
    point_uuid,
)
from veupath_chatbot.integrations.veupathdb.client import (
    encode_context_param_values_for_wdk,
)
from veupath_chatbot.integrations.veupathdb.wdk_parameters import WDKEnumParam
from veupath_chatbot.platform.errors import WDKError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_store(*, cached_payload: dict[str, Any] | None = None) -> MagicMock:
    store = MagicMock()
    store.ensure_collection = AsyncMock()
    store.upsert = AsyncMock()
    if cached_payload is not None:
        store.get = AsyncMock(
            return_value={"id": "some-id", "payload": cached_payload, "vector": []}
        )
    else:
        store.get = AsyncMock(return_value=None)
    return store


def _default_param_response() -> list[WDKEnumParam]:
    """Default mock response: a single enum parameter with vocabulary."""
    return [
        WDKEnumParam(
            name="organism",
            display_name="Organism",
            type="single-pick-vocabulary",
            vocabulary=[["Plasmodium falciparum 3D7", "P. falciparum 3D7"]],
        ),
    ]


def _mock_wdk_client(response: list[Any] | None = None) -> MagicMock:
    client = MagicMock()
    client.base_url = "https://plasmodb.org/plasmo/service"
    client.get_refreshed_dependent_params = AsyncMock(
        return_value=response if response is not None else _default_param_response()
    )
    return client


def _patches(
    store: MagicMock,
    wdk_client: MagicMock | None = None,
    portal_client: MagicMock | None = None,
    embed_vec: list[float] | None = None,
):
    """Return a combined patch context manager for the cache function."""

    @contextmanager
    def _ctx():
        embed = AsyncMock(return_value=embed_vec or [0.1, 0.2, 0.3])
        settings = MagicMock()
        settings.embeddings_model = "text-embedding-3-small"

        wdk = wdk_client or _mock_wdk_client()

        def _get_wdk_client(site_id: str) -> MagicMock:
            if portal_client is not None and site_id == "veupathdb":
                return portal_client
            return wdk

        with (
            patch(
                "veupath_chatbot.integrations.vectorstore.dependent_vocab_cache.embed_one",
                embed,
            ),
            patch(
                "veupath_chatbot.integrations.vectorstore.dependent_vocab_cache.get_embedding_dim",
                AsyncMock(return_value=1536),
            ),
            patch(
                "veupath_chatbot.integrations.vectorstore.dependent_vocab_cache.get_settings",
                return_value=settings,
            ),
            patch(
                "veupath_chatbot.integrations.vectorstore.dependent_vocab_cache.get_wdk_client",
                side_effect=_get_wdk_client,
            ),
            patch(
                "veupath_chatbot.integrations.vectorstore.dependent_vocab_cache.QdrantStore.from_settings",
                return_value=store,
            ),
        ):
            yield

    return _ctx()


# ---------------------------------------------------------------------------
# Cache key determinism
# ---------------------------------------------------------------------------


class TestCacheKeyDeterminism:
    """The cache key is site:rt:search:param:contextHash.
    Verify that identical context values (potentially re-ordered) produce
    the same point UUID.
    """

    def test_same_context_same_key(self) -> None:
        ctx_a = encode_context_param_values_for_wdk({"x": "1", "y": "2"})
        ctx_b = encode_context_param_values_for_wdk({"y": "2", "x": "1"})
        ch_a = context_hash(ctx_a)
        ch_b = context_hash(ctx_b)
        assert ch_a == ch_b

        key_a = f"site:rt:search:param:{ch_a}"
        key_b = f"site:rt:search:param:{ch_b}"
        assert point_uuid(key_a) == point_uuid(key_b)

    def test_different_context_different_key(self) -> None:
        ctx_a = encode_context_param_values_for_wdk({"x": "1"})
        ctx_b = encode_context_param_values_for_wdk({"x": "2"})
        assert context_hash(ctx_a) != context_hash(ctx_b)

    def test_empty_context(self) -> None:
        ctx = encode_context_param_values_for_wdk({})
        ch = context_hash(ctx)
        assert len(ch) == 64  # sha256 hex


# ---------------------------------------------------------------------------
# Cache hit
# ---------------------------------------------------------------------------


class TestCacheHit:
    async def test_returns_cached_payload_on_hit(self) -> None:
        cached_payload = {
            "siteId": "plasmodb",
            "wdkResponse": {"vocab": ["a", "b"]},
        }
        store = _mock_store(cached_payload=cached_payload)
        with _patches(store):
            result = await get_dependent_vocab_authoritative_cached(
                SearchContext("plasmodb", "gene", "GenesByTaxon"),
                param_name="organism",
                context_values={"taxon": "Plasmodium"},
                store=store,
            )

        assert result["cache"] == "hit"
        assert result["siteId"] == "plasmodb"
        # Verify upsert was NOT called (cache hit should skip WDK call)
        store.upsert.assert_not_called()


# ---------------------------------------------------------------------------
# Cache miss
# ---------------------------------------------------------------------------


class TestCacheMiss:
    async def test_calls_wdk_and_upserts_on_miss(self) -> None:
        wdk_client = _mock_wdk_client()
        store = _mock_store(cached_payload=None)

        with _patches(store, wdk_client=wdk_client):
            result = await get_dependent_vocab_authoritative_cached(
                SearchContext("plasmodb", "gene", "GenesByTaxon"),
                param_name="organism",
                context_values={},
                store=store,
            )

        assert result["cache"] == "miss"
        # wdkResponse is now a serialized list of parameter dicts
        wdk_resp = result["wdkResponse"]
        assert isinstance(wdk_resp, list)
        assert len(wdk_resp) == 1
        assert wdk_resp[0]["name"] == "organism"
        assert result["siteId"] == "plasmodb"
        assert result["recordType"] == "gene"
        assert result["searchName"] == "GenesByTaxon"
        assert result["paramName"] == "organism"
        store.upsert.assert_called_once()


# ---------------------------------------------------------------------------
# Portal fallback
# ---------------------------------------------------------------------------


class TestPortalFallback:
    async def test_falls_back_to_portal_on_wdk_error(self) -> None:
        """When the site-specific client fails with WDKError, it should
        fall back to the veupathdb portal client."""
        failing_client = MagicMock()
        failing_client.base_url = "https://plasmodb.org/plasmo/service"
        failing_client.get_refreshed_dependent_params = AsyncMock(
            side_effect=WDKError("fail")
        )

        portal_client = _mock_wdk_client()

        store = _mock_store(cached_payload=None)

        with _patches(store, wdk_client=failing_client, portal_client=portal_client):
            result = await get_dependent_vocab_authoritative_cached(
                SearchContext("plasmodb", "gene", "GenesByTaxon"),
                param_name="organism",
                context_values={},
                store=store,
            )

        assert result["cache"] == "miss"
        wdk_resp = result["wdkResponse"]
        assert isinstance(wdk_resp, list)
        assert len(wdk_resp) == 1

    async def test_no_fallback_when_already_veupathdb(self) -> None:
        """When site_id == 'veupathdb' and WDKError occurs, it should re-raise."""
        failing_client = MagicMock()
        failing_client.base_url = "https://veupathdb.org/veupathdb/service"
        failing_client.get_refreshed_dependent_params = AsyncMock(
            side_effect=WDKError("fail")
        )

        store = _mock_store(cached_payload=None)

        with _patches(store, wdk_client=failing_client), pytest.raises(WDKError):
            await get_dependent_vocab_authoritative_cached(
                SearchContext("veupathdb", "gene", "GenesByTaxon"),
                param_name="organism",
                context_values={},
                store=store,
            )


# ---------------------------------------------------------------------------
# ensure_dependent_vocab_collection
# ---------------------------------------------------------------------------


class TestEnsureDependentVocabCollection:
    async def test_calls_ensure_collection_known_model(self) -> None:
        """With a known model, get_embedding_dim resolves locally (no embed call)."""
        store = MagicMock()
        store.ensure_collection = AsyncMock()

        with patch(
            "veupath_chatbot.integrations.vectorstore.dependent_vocab_cache.get_settings",
            return_value=MagicMock(embeddings_model="text-embedding-3-small"),
        ):
            await ensure_dependent_vocab_collection(store)

        store.ensure_collection.assert_called_once()
        call_kwargs = store.ensure_collection.call_args[1]
        assert call_kwargs["name"] == "wdk_dependent_vocab_cache_v1"
        assert call_kwargs["vector_size"] == 1536

    async def test_calls_ensure_collection_unknown_model(self) -> None:
        """With an unknown model, get_embedding_dim falls back to embed_one."""
        store = MagicMock()
        store.ensure_collection = AsyncMock()
        embed_vec = [0.1] * 768

        # Remove any cached entry so embed_one is actually called.
        _KNOWN_DIMS.pop("some-custom-model", None)

        with (
            patch(
                "veupath_chatbot.integrations.vectorstore.bootstrap.embed_one",
                AsyncMock(return_value=embed_vec),
            ),
            patch(
                "veupath_chatbot.integrations.vectorstore.dependent_vocab_cache.get_settings",
                return_value=MagicMock(embeddings_model="some-custom-model"),
            ),
        ):
            await ensure_dependent_vocab_collection(store)

        # Clean up the cache to avoid leaking into other tests.
        _KNOWN_DIMS.pop("some-custom-model", None)

        store.ensure_collection.assert_called_once()
        call_kwargs = store.ensure_collection.call_args[1]
        assert call_kwargs["name"] == "wdk_dependent_vocab_cache_v1"
        assert call_kwargs["vector_size"] == 768

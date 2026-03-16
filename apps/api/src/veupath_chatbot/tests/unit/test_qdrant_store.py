"""Tests for QdrantStore shared client lifecycle.

Covers:
  - Shared client is lazily created on first connect()
  - Subsequent connect() calls reuse the same client instance
  - connect() does NOT close the shared client on context exit
  - close() properly cleans up the shared client
  - After close(), connect() creates a fresh client (re-initialization)
  - _get_client() is idempotent (same instance returned)
  - close_all_qdrant_stores() closes every registered store
"""

from unittest.mock import AsyncMock, patch

import pytest

from veupath_chatbot.integrations.vectorstore.qdrant_store import (
    QdrantStore,
    _active_stores,
    close_all_qdrant_stores,
)


class TestSharedClientReuse:
    """Verify connect() reuses a single shared client across calls."""

    @pytest.mark.asyncio
    async def test_connect_returns_same_client_instance(self) -> None:
        store = QdrantStore(url="http://localhost:6333")
        async with store.connect() as client1:
            pass
        async with store.connect() as client2:
            pass
        assert client1 is client2

    @pytest.mark.asyncio
    async def test_concurrent_connect_returns_same_instance(self) -> None:
        store = QdrantStore(url="http://localhost:6333")
        async with store.connect() as client1, store.connect() as client2:
            assert client1 is client2

    @pytest.mark.asyncio
    async def test_get_client_idempotent(self) -> None:
        store = QdrantStore(url="http://localhost:6333")
        c1 = store._get_client()
        c2 = store._get_client()
        assert c1 is c2
        # Cleanup
        await store.close()


class TestConnectDoesNotCloseClient:
    """Verify connect() context exit does NOT close the shared client."""

    @pytest.mark.asyncio
    async def test_client_still_usable_after_connect_exit(self) -> None:
        store = QdrantStore(url="http://localhost:6333")
        async with store.connect() as client:
            pass
        # Client should still be the shared client (not closed/replaced)
        assert store._shared_client is client
        assert store._shared_client is not None
        # Cleanup
        await store.close()


class TestCloseCleanup:
    """Verify close() properly releases the shared client."""

    @pytest.mark.asyncio
    async def test_close_sets_shared_client_to_none(self) -> None:
        store = QdrantStore(url="http://localhost:6333")
        # Force client creation
        async with store.connect():
            pass
        assert store._shared_client is not None
        await store.close()
        assert store._shared_client is None

    @pytest.mark.asyncio
    async def test_close_calls_client_close(self) -> None:
        store = QdrantStore(url="http://localhost:6333")
        mock_client = AsyncMock()
        store._shared_client = mock_client
        await store.close()
        mock_client.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_when_no_client_is_noop(self) -> None:
        store = QdrantStore(url="http://localhost:6333")
        assert store._shared_client is None
        # Should not raise
        await store.close()
        assert store._shared_client is None


class TestReinitialization:
    """Verify connect() creates a fresh client after close()."""

    @pytest.mark.asyncio
    async def test_connect_after_close_creates_new_client(self) -> None:
        store = QdrantStore(url="http://localhost:6333")
        async with store.connect() as client1:
            pass
        await store.close()
        async with store.connect() as client2:
            pass
        assert client1 is not client2
        assert store._shared_client is client2
        # Cleanup
        await store.close()


class TestFromSettings:
    """Verify from_settings() produces a working QdrantStore."""

    @pytest.mark.asyncio
    async def test_from_settings_creates_store(self) -> None:
        with patch(
            "veupath_chatbot.integrations.vectorstore.qdrant_store.get_settings"
        ) as mock_settings:
            mock_settings.return_value.qdrant_url = "http://test:6333"
            mock_settings.return_value.qdrant_api_key = None
            mock_settings.return_value.qdrant_timeout_seconds = 10
            store = QdrantStore.from_settings()
        assert store.url == "http://test:6333"
        assert store.api_key is None
        assert store._shared_client is None


class TestActiveStoresRegistry:
    """Verify from_settings() registers stores for shutdown cleanup."""

    @pytest.mark.asyncio
    async def test_from_settings_registers_store(self) -> None:
        initial_count = len(_active_stores)
        with patch(
            "veupath_chatbot.integrations.vectorstore.qdrant_store.get_settings"
        ) as mock_settings:
            mock_settings.return_value.qdrant_url = "http://reg-test:6333"
            mock_settings.return_value.qdrant_api_key = None
            mock_settings.return_value.qdrant_timeout_seconds = 5
            store = QdrantStore.from_settings()
        assert store in _active_stores
        assert len(_active_stores) == initial_count + 1
        # Cleanup: remove from registry to avoid polluting other tests
        _active_stores.remove(store)

    @pytest.mark.asyncio
    async def test_close_all_closes_every_store(self) -> None:
        store_a = QdrantStore(url="http://a:6333")
        store_b = QdrantStore(url="http://b:6333")
        mock_a = AsyncMock()
        mock_b = AsyncMock()
        store_a._shared_client = mock_a
        store_b._shared_client = mock_b
        _active_stores.append(store_a)
        _active_stores.append(store_b)
        await close_all_qdrant_stores()
        mock_a.close.assert_awaited_once()
        mock_b.close.assert_awaited_once()
        assert store_a._shared_client is None
        assert store_b._shared_client is None
        assert len(_active_stores) == 0

    @pytest.mark.asyncio
    async def test_close_all_is_idempotent(self) -> None:
        await close_all_qdrant_stores()
        assert len(_active_stores) == 0
        # Second call should not raise
        await close_all_qdrant_stores()
        assert len(_active_stores) == 0

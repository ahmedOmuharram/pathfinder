"""Unit tests for platform.store -- WriteThruStore generic store."""

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from veupath_chatbot.platform.store import WriteThruStore


@dataclass
class FakeEntity:
    id: str
    name: str


@dataclass
class FakeRow:
    """Fake ORM row for testing DB-backed methods."""

    id: str
    name: str


class FakeRowModel:
    """Fake SQLAlchemy model class for testing."""

    id = "id"
    __tablename__ = "fake_entities"


def _fake_to_row(entity: FakeEntity) -> dict[str, object]:
    return {"id": entity.id, "name": entity.name}


def _fake_from_row(row: FakeRow) -> FakeEntity:
    return FakeEntity(id=row.id, name=row.name)


class FakeStore(WriteThruStore[FakeEntity]):
    """Concrete store for testing with _model, _to_row, _from_row."""

    _model = FakeRowModel
    _to_row = staticmethod(_fake_to_row)
    _from_row = staticmethod(_fake_from_row)


class TestWriteThruStoreSync:
    """Sync interface: save, get, delete."""

    def test_get_returns_none_when_empty(self) -> None:
        store = FakeStore()
        assert store.get("nonexistent") is None

    def test_save_stores_in_cache(self) -> None:
        store = FakeStore()
        entity = FakeEntity(id="abc", name="Test")
        store.save(entity)

        assert store.get("abc") is entity

    def test_save_overwrites_existing(self) -> None:
        store = FakeStore()
        e1 = FakeEntity(id="abc", name="V1")
        e2 = FakeEntity(id="abc", name="V2")
        store.save(e1)
        store.save(e2)

        result = store.get("abc")
        assert result is e2
        assert result.name == "V2"

    def test_delete_removes_from_cache(self) -> None:
        store = FakeStore()
        entity = FakeEntity(id="abc", name="Test")
        store.save(entity)
        assert store.get("abc") is entity

        removed = store.delete("abc")
        assert removed is True
        assert store.get("abc") is None

    def test_delete_nonexistent_returns_false(self) -> None:
        store = FakeStore()
        removed = store.delete("nonexistent")
        assert removed is False

    def test_delete_spawns_db_delete(self) -> None:
        """save+delete should run without error (spawn fires via _eager_spawn)."""
        store = FakeStore()
        entity = FakeEntity(id="abc", name="Test")
        store.save(entity)
        store.delete("abc")
        assert store.get("abc") is None

    def test_save_stores_and_can_retrieve(self) -> None:
        store = FakeStore()
        entity = FakeEntity(id="xyz", name="Named")
        store.save(entity)
        assert store.get("xyz") is entity

    def test_delete_removes_cache_entry(self) -> None:
        store = FakeStore()
        store._cache["xyz"] = FakeEntity(id="xyz", name="X")
        store.delete("xyz")
        assert store.get("xyz") is None


class TestWriteThruStoreAsync:
    """Async interface: aget, adelete."""

    async def test_aget_returns_cached_entity(self) -> None:
        store = FakeStore()
        entity = FakeEntity(id="abc", name="Cached")
        store._cache["abc"] = entity

        result = await store.aget("abc")
        assert result is entity

    async def test_aget_loads_from_db_on_cache_miss(self) -> None:
        store = FakeStore()
        db_entity = FakeEntity(id="abc", name="FromDB")

        with patch.object(
            store, "_load", new_callable=AsyncMock, return_value=db_entity
        ):
            result = await store.aget("abc")

        assert result is db_entity
        assert result.name == "FromDB"
        assert store._cache["abc"] is db_entity

    async def test_aget_returns_none_when_not_in_db(self) -> None:
        store = FakeStore()

        with patch.object(store, "_load", new_callable=AsyncMock, return_value=None):
            result = await store.aget("missing")

        assert result is None
        assert "missing" not in store._cache

    async def test_adelete_calls_db_delete(self) -> None:
        store = FakeStore()
        store._cache["abc"] = FakeEntity(id="abc", name="Test")

        with patch.object(store, "_delete_from_db", new_callable=AsyncMock):
            result = await store.adelete("abc")

        assert result is True
        assert "abc" not in store._cache

    async def test_adelete_returns_false_for_nonexistent(self) -> None:
        store = FakeStore()

        with patch.object(store, "_delete_from_db", new_callable=AsyncMock):
            result = await store.adelete("nonexistent")

        assert result is False

    async def test_aget_after_cache_set_uses_cache(self) -> None:
        store = FakeStore()
        entity = FakeEntity(id="abc", name="Saved")
        store._cache["abc"] = entity

        result = await store.aget("abc")
        assert result is entity

    async def test_aget_caches_loaded_entity_for_subsequent_calls(self) -> None:
        store = FakeStore()
        db_entity = FakeEntity(id="abc", name="FromDB")
        load_mock = AsyncMock(return_value=db_entity)

        with patch.object(store, "_load", load_mock):
            result1 = await store.aget("abc")
            assert result1 is db_entity

        # Second call should use cache (no mock needed)
        result2 = await store.aget("abc")
        assert result2 is db_entity

    async def test_adelete_removes_from_cache_and_calls_db(self) -> None:
        store = FakeStore()
        store._cache["abc"] = FakeEntity(id="abc", name="X")

        with patch.object(store, "_delete_from_db", new_callable=AsyncMock):
            await store.adelete("abc")

        assert "abc" not in store._cache


# ---------------------------------------------------------------------------
# DB method tests (testing _persist, _load, _delete_from_db directly)
# ---------------------------------------------------------------------------


class TestWriteThruStoreDbMethods:
    """Tests for the built-in DB helper methods derived from _model/_to_row/_from_row."""

    async def test_persist_calls_upsert(self) -> None:
        """_persist should call pg_insert and on_conflict_do_update."""
        store = FakeStore()
        entity = FakeEntity(id="abc", name="Test")

        mock_session = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_ctx)

        with (
            patch(
                "veupath_chatbot.platform.store.async_session_factory",
                mock_factory,
            ),
            patch("veupath_chatbot.platform.store.pg_insert") as mock_insert,
        ):
            mock_stmt = MagicMock()
            mock_insert.return_value = mock_stmt
            mock_stmt.values.return_value = mock_stmt
            mock_stmt.on_conflict_do_update.return_value = mock_stmt

            await store._persist(entity)

    async def test_load_returns_entity_when_found(self) -> None:
        store = FakeStore()
        fake_row = FakeRow(id="abc", name="FromDB")

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=fake_row)
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_ctx)

        with patch(
            "veupath_chatbot.platform.store.async_session_factory",
            mock_factory,
        ):
            result = await store._load("abc")

        assert result is not None
        assert result.id == "abc"
        assert result.name == "FromDB"

    async def test_load_returns_none_when_not_found(self) -> None:
        store = FakeStore()

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=None)
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_ctx)

        with patch(
            "veupath_chatbot.platform.store.async_session_factory",
            mock_factory,
        ):
            result = await store._load("nonexistent")

        assert result is None

    async def test_delete_from_db_executes_delete(self) -> None:
        store = FakeStore()

        mock_session = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_ctx)

        with (
            patch(
                "veupath_chatbot.platform.store.async_session_factory",
                mock_factory,
            ),
            patch("veupath_chatbot.platform.store.sa_delete") as mock_delete,
        ):
            mock_stmt = MagicMock()
            mock_delete.return_value = mock_stmt
            mock_stmt.where.return_value = mock_stmt

            await store._delete_from_db("abc")

    async def test_persist_logs_on_exception(self) -> None:
        """_persist should catch exceptions and log them."""
        store = FakeStore()
        entity = FakeEntity(id="abc", name="Test")

        with patch(
            "veupath_chatbot.platform.store.async_session_factory",
            side_effect=RuntimeError("DB down"),
        ):
            await store._persist(entity)  # Should not raise

    def test_subclass_with_model_and_converters(self) -> None:
        """Subclass with _model, _to_row, _from_row works with cache ops."""
        store = FakeStore()
        entity = FakeEntity(id="x", name="Y")
        store.save(entity)
        assert store.get("x") is entity


# ---------------------------------------------------------------------------
# Retry & resilience tests
# ---------------------------------------------------------------------------


class TestWriteThruStoreRetry:
    """Tests for retry behavior on transient DB failures."""

    async def test_persist_retries_on_transient_failure(self) -> None:
        """_persist should retry on transient DB errors before giving up."""
        store = FakeStore()
        entity = FakeEntity(id="abc", name="Test")

        mock_ctx_manager = AsyncMock()
        # First two calls raise, third succeeds
        good_session = AsyncMock()
        mock_ctx_manager.__aenter__ = AsyncMock(
            side_effect=[
                ConnectionError("DB connection lost"),
                ConnectionError("DB connection lost"),
                good_session,
            ]
        )
        mock_ctx_manager.__aexit__ = AsyncMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_ctx_manager)

        with (
            patch(
                "veupath_chatbot.platform.store.async_session_factory",
                mock_factory,
            ),
            patch("veupath_chatbot.platform.store.pg_insert") as mock_insert,
        ):
            mock_stmt = MagicMock()
            mock_insert.return_value = mock_stmt
            mock_stmt.values.return_value = mock_stmt
            mock_stmt.on_conflict_do_update.return_value = mock_stmt

            # Should not raise — retries succeed on 3rd attempt
            await store._persist(entity)

    async def test_persist_gives_up_after_max_retries(self) -> None:
        """_persist should log after exhausting all retry attempts."""
        store = FakeStore()
        entity = FakeEntity(id="abc", name="Test")

        mock_ctx_manager = AsyncMock()
        mock_ctx_manager.__aenter__ = AsyncMock(
            side_effect=ConnectionError("DB permanently down")
        )
        mock_ctx_manager.__aexit__ = AsyncMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_ctx_manager)

        with (
            patch(
                "veupath_chatbot.platform.store.async_session_factory",
                mock_factory,
            ),
            patch("veupath_chatbot.platform.store.pg_insert") as mock_insert,
        ):
            mock_stmt = MagicMock()
            mock_insert.return_value = mock_stmt
            mock_stmt.values.return_value = mock_stmt
            mock_stmt.on_conflict_do_update.return_value = mock_stmt

            # Should not raise — catches and logs after exhausting retries
            await store._persist(entity)

    async def test_delete_from_db_retries_on_transient_failure(self) -> None:
        """_delete_from_db should retry on transient errors."""
        store = FakeStore()

        good_session = AsyncMock()
        mock_ctx_manager = AsyncMock()
        mock_ctx_manager.__aenter__ = AsyncMock(
            side_effect=[
                ConnectionError("DB connection lost"),
                good_session,
            ]
        )
        mock_ctx_manager.__aexit__ = AsyncMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_ctx_manager)

        with (
            patch(
                "veupath_chatbot.platform.store.async_session_factory",
                mock_factory,
            ),
            patch("veupath_chatbot.platform.store.sa_delete") as mock_delete,
        ):
            mock_stmt = MagicMock()
            mock_delete.return_value = mock_stmt
            mock_stmt.where.return_value = mock_stmt

            # Should not raise — retries succeed on 2nd attempt
            await store._delete_from_db("abc")

    async def test_delete_from_db_logs_on_final_failure(self) -> None:
        """_delete_from_db should log after exhausting retries, not raise."""
        store = FakeStore()

        mock_ctx_manager = AsyncMock()
        mock_ctx_manager.__aenter__ = AsyncMock(
            side_effect=ConnectionError("DB permanently down")
        )
        mock_ctx_manager.__aexit__ = AsyncMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_ctx_manager)

        with (
            patch(
                "veupath_chatbot.platform.store.async_session_factory",
                mock_factory,
            ),
            patch("veupath_chatbot.platform.store.sa_delete") as mock_delete,
        ):
            mock_stmt = MagicMock()
            mock_delete.return_value = mock_stmt
            mock_stmt.where.return_value = mock_stmt

            # Should NOT raise — must catch and log after exhausting retries
            await store._delete_from_db("abc")

    async def test_persist_reraises_original_exception_not_retry_error(
        self,
    ) -> None:
        """After retries exhaust, _persist_with_retry must raise the original
        exception (e.g. ConnectionError), NOT tenacity.RetryError.

        reraise=True preserves diagnostic info so _persist's logger.exception
        captures the real root cause.
        """
        store = FakeStore()
        entity = FakeEntity(id="abc", name="Test")

        mock_ctx_manager = AsyncMock()
        mock_ctx_manager.__aenter__ = AsyncMock(
            side_effect=ConnectionError("DB permanently down")
        )
        mock_ctx_manager.__aexit__ = AsyncMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_ctx_manager)

        mock_insert = MagicMock()
        mock_stmt = MagicMock()
        mock_insert.return_value = mock_stmt
        mock_stmt.values.return_value = mock_stmt
        mock_stmt.on_conflict_do_update.return_value = mock_stmt

        with (
            patch(
                "veupath_chatbot.platform.store.async_session_factory",
                mock_factory,
            ),
            patch("veupath_chatbot.platform.store.pg_insert", mock_insert),
            pytest.raises(ConnectionError, match="DB permanently down"),
        ):
            await store._persist_with_retry(entity)

    async def test_delete_reraises_original_exception_not_retry_error(
        self,
    ) -> None:
        """After retries exhaust, _delete_from_db_with_retry must raise the
        original exception, NOT tenacity.RetryError."""
        store = FakeStore()

        mock_ctx_manager = AsyncMock()
        mock_ctx_manager.__aenter__ = AsyncMock(
            side_effect=ConnectionError("DB permanently down")
        )
        mock_ctx_manager.__aexit__ = AsyncMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_ctx_manager)

        mock_delete = MagicMock()
        mock_stmt = MagicMock()
        mock_delete.return_value = mock_stmt
        mock_stmt.where.return_value = mock_stmt

        with (
            patch(
                "veupath_chatbot.platform.store.async_session_factory",
                mock_factory,
            ),
            patch("veupath_chatbot.platform.store.sa_delete", mock_delete),
            pytest.raises(ConnectionError, match="DB permanently down"),
        ):
            await store._delete_from_db_with_retry("abc")

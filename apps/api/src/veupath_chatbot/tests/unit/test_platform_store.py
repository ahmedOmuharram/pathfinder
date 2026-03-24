"""Unit tests for platform.store -- WriteThruStore generic store."""

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

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

    @patch("veupath_chatbot.platform.store.spawn")
    def test_get_returns_none_when_empty(self, mock_spawn: MagicMock) -> None:
        store = FakeStore()
        assert store.get("nonexistent") is None

    @patch("veupath_chatbot.platform.store.spawn")
    def test_save_stores_in_cache(self, mock_spawn: MagicMock) -> None:
        store = FakeStore()
        entity = FakeEntity(id="abc", name="Test")
        store.save(entity)

        assert store.get("abc") is entity
        mock_spawn.assert_called_once()

    @patch("veupath_chatbot.platform.store.spawn")
    def test_save_overwrites_existing(self, mock_spawn: MagicMock) -> None:
        store = FakeStore()
        e1 = FakeEntity(id="abc", name="V1")
        e2 = FakeEntity(id="abc", name="V2")
        store.save(e1)
        store.save(e2)

        result = store.get("abc")
        assert result is e2
        assert result.name == "V2"

    @patch("veupath_chatbot.platform.store.spawn")
    def test_delete_removes_from_cache(self, mock_spawn: MagicMock) -> None:
        store = FakeStore()
        entity = FakeEntity(id="abc", name="Test")
        store.save(entity)
        assert store.get("abc") is entity

        removed = store.delete("abc")
        assert removed is True
        assert store.get("abc") is None

    @patch("veupath_chatbot.platform.store.spawn")
    def test_delete_nonexistent_returns_false(self, mock_spawn: MagicMock) -> None:
        store = FakeStore()
        removed = store.delete("nonexistent")
        assert removed is False
        mock_spawn.assert_not_called()

    @patch("veupath_chatbot.platform.store.spawn")
    def test_delete_nonexistent_does_not_spawn_task(
        self, mock_spawn: MagicMock
    ) -> None:
        """Deleting a cache-miss entity must NOT fire a wasteful DB delete."""
        store = FakeStore()
        store.delete("ghost")
        mock_spawn.assert_not_called()

    @patch("veupath_chatbot.platform.store.spawn")
    def test_delete_spawns_db_delete(self, mock_spawn: MagicMock) -> None:
        store = FakeStore()
        entity = FakeEntity(id="abc", name="Test")
        store.save(entity)
        mock_spawn.reset_mock()

        store.delete("abc")
        mock_spawn.assert_called_once()

    @patch("veupath_chatbot.platform.store.spawn")
    def test_save_calls_spawn_with_persist_name(self, mock_spawn: MagicMock) -> None:
        store = FakeStore()
        entity = FakeEntity(id="xyz", name="Named")
        store.save(entity)

        call_kwargs = mock_spawn.call_args
        assert call_kwargs[1]["name"] == "persist-xyz"

    @patch("veupath_chatbot.platform.store.spawn")
    def test_delete_calls_spawn_with_delete_name(self, mock_spawn: MagicMock) -> None:
        store = FakeStore()
        store._cache["xyz"] = FakeEntity(id="xyz", name="X")
        store.delete("xyz")

        call_kwargs = mock_spawn.call_args
        assert call_kwargs[1]["name"] == "delete-xyz"


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

        with patch.object(store, "_delete_from_db", new_callable=AsyncMock) as mock_del:
            result = await store.adelete("abc")

        assert result is True
        assert "abc" not in store._cache
        mock_del.assert_called_once_with("abc")

    async def test_adelete_returns_false_for_nonexistent(self) -> None:
        store = FakeStore()

        with patch.object(store, "_delete_from_db", new_callable=AsyncMock) as mock_del:
            result = await store.adelete("nonexistent")

        assert result is False
        mock_del.assert_called_once_with("nonexistent")

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
            await store.aget("abc")
            assert load_mock.call_count == 1

        # Second call should use cache (no mock needed)
        result = await store.aget("abc")
        assert result is db_entity

    async def test_adelete_removes_from_cache_and_calls_db(self) -> None:
        store = FakeStore()
        store._cache["abc"] = FakeEntity(id="abc", name="X")

        with patch.object(store, "_delete_from_db", new_callable=AsyncMock) as mock_del:
            await store.adelete("abc")

        assert "abc" not in store._cache
        mock_del.assert_called_once_with("abc")


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

            mock_insert.assert_called_once_with(FakeRowModel)
            mock_stmt.values.assert_called_once_with(id="abc", name="Test")
            mock_session.execute.assert_called_once()
            mock_session.commit.assert_called_once()

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
        mock_session.get.assert_called_once_with(FakeRowModel, "abc")

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

            mock_delete.assert_called_once_with(FakeRowModel)
            mock_session.execute.assert_called_once()
            mock_session.commit.assert_called_once()

    async def test_persist_logs_on_exception(self) -> None:
        """_persist should catch exceptions and log them."""
        store = FakeStore()
        entity = FakeEntity(id="abc", name="Test")

        with (
            patch(
                "veupath_chatbot.platform.store.async_session_factory",
                side_effect=RuntimeError("DB down"),
            ),
            patch("veupath_chatbot.platform.store.logger") as mock_logger,
        ):
            await store._persist(entity)  # Should not raise

            mock_logger.exception.assert_called_once()

    def test_subclass_with_model_and_converters(self) -> None:
        """Subclass with _model, _to_row, _from_row works with cache ops."""
        store = FakeStore()
        with patch("veupath_chatbot.platform.store.spawn"):
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

            await store._persist(entity)

            # Should have been called 3 times (2 failures + 1 success)
            assert mock_factory.call_count == 3
            good_session.execute.assert_called_once()
            good_session.commit.assert_called_once()

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
            patch("veupath_chatbot.platform.store.logger") as mock_logger,
        ):
            mock_stmt = MagicMock()
            mock_insert.return_value = mock_stmt
            mock_stmt.values.return_value = mock_stmt
            mock_stmt.on_conflict_do_update.return_value = mock_stmt

            await store._persist(entity)  # Should not raise

            # Should have retried multiple times
            assert mock_factory.call_count > 1
            mock_logger.exception.assert_called_once()

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

            await store._delete_from_db("abc")

            assert mock_factory.call_count == 2
            good_session.execute.assert_called_once()
            good_session.commit.assert_called_once()

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
            patch("veupath_chatbot.platform.store.logger") as mock_logger,
        ):
            mock_stmt = MagicMock()
            mock_delete.return_value = mock_stmt
            mock_stmt.where.return_value = mock_stmt

            # Should NOT raise — must catch and log
            await store._delete_from_db("abc")

            assert mock_factory.call_count > 1
            mock_logger.exception.assert_called_once()

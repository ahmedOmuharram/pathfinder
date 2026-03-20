"""Tests for GeneSetStore."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

from veupath_chatbot.services.gene_sets.store import GeneSetStore
from veupath_chatbot.services.gene_sets.types import GeneSet

_USER_A = uuid4()
_USER_B = uuid4()


def _make_set(
    set_id: str = "gs-1",
    site_id: str = "plasmo",
    gene_ids: list[str] | None = None,
    user_id: UUID | None = None,
    created_at: datetime | None = None,
) -> GeneSet:
    return GeneSet(
        id=set_id,
        name=f"Test Set {set_id}",
        site_id=site_id,
        gene_ids=gene_ids or ["GENE1", "GENE2"],
        source="paste",
        user_id=user_id,
        created_at=created_at or datetime.now(UTC),
    )


class TestSyncCrud:
    def test_save_and_get(self) -> None:
        store = GeneSetStore()
        gs = _make_set()
        store.save(gs)
        assert store.get("gs-1") is gs

    def test_get_missing_returns_none(self) -> None:
        store = GeneSetStore()
        assert store.get("nonexistent") is None

    def test_save_overwrites(self) -> None:
        store = GeneSetStore()
        gs1 = _make_set("a")
        gs2 = _make_set("a")
        store.save(gs1)
        store.save(gs2)
        assert store.get("a") is gs2

    def test_delete(self) -> None:
        store = GeneSetStore()
        store.save(_make_set("a"))
        assert store.delete("a") is True
        assert store.get("a") is None

    def test_delete_missing_returns_false(self) -> None:
        store = GeneSetStore()
        assert store.delete("nope") is False


class TestListAll:
    def test_returns_all(self) -> None:
        store = GeneSetStore()
        store.save(_make_set("a"))
        store.save(_make_set("b"))
        assert len(store.list_all()) == 2

    def test_filters_by_site(self) -> None:
        store = GeneSetStore()
        store.save(_make_set("a", site_id="plasmo"))
        store.save(_make_set("b", site_id="toxo"))
        assert len(store.list_all(site_id="plasmo")) == 1

    def test_sorted_newest_first(self) -> None:
        store = GeneSetStore()
        store.save(_make_set("old", created_at=datetime(2024, 1, 1, tzinfo=UTC)))
        store.save(_make_set("new", created_at=datetime(2025, 1, 1, tzinfo=UTC)))
        result = store.list_all()
        assert result[0].id == "new"
        assert result[1].id == "old"

    def test_empty_store(self) -> None:
        store = GeneSetStore()
        assert store.list_all() == []

    def test_no_match_returns_empty(self) -> None:
        store = GeneSetStore()
        store.save(_make_set("a", site_id="plasmo"))
        assert store.list_all(site_id="nonexistent") == []


class TestListForUser:
    def test_filters_by_user(self) -> None:
        store = GeneSetStore()
        store.save(_make_set("a", user_id=_USER_A))
        store.save(_make_set("b", user_id=_USER_B))
        result = store.list_for_user(_USER_A)
        assert len(result) == 1
        assert result[0].id == "a"

    def test_filters_by_user_and_site(self) -> None:
        store = GeneSetStore()
        store.save(_make_set("a", user_id=_USER_A, site_id="plasmo"))
        store.save(_make_set("b", user_id=_USER_A, site_id="toxo"))
        store.save(_make_set("c", user_id=_USER_B, site_id="plasmo"))
        result = store.list_for_user(_USER_A, site_id="plasmo")
        assert len(result) == 1
        assert result[0].id == "a"

    def test_no_match_returns_empty(self) -> None:
        store = GeneSetStore()
        store.save(_make_set("a", user_id=_USER_A))
        assert store.list_for_user(_USER_B) == []

    def test_sorted_newest_first(self) -> None:
        store = GeneSetStore()
        store.save(
            _make_set(
                "old", user_id=_USER_A, created_at=datetime(2024, 1, 1, tzinfo=UTC)
            )
        )
        store.save(
            _make_set(
                "new", user_id=_USER_A, created_at=datetime(2025, 1, 1, tzinfo=UTC)
            )
        )
        result = store.list_for_user(_USER_A)
        assert result[0].id == "new"

    def test_excludes_none_user_id(self) -> None:
        store = GeneSetStore()
        store.save(_make_set("a", user_id=None))
        store.save(_make_set("b", user_id=_USER_A))
        result = store.list_for_user(_USER_A)
        assert len(result) == 1
        assert result[0].id == "b"


class TestAsyncGet:
    async def test_returns_from_cache(self) -> None:
        store = GeneSetStore()
        gs = _make_set("cached")
        store.save(gs)
        result = await store.aget("cached")
        assert result is gs

    async def test_falls_back_to_db_on_cache_miss(self) -> None:
        store = GeneSetStore()
        db_set = _make_set("db-only")

        with patch.object(store, "_load", new_callable=AsyncMock, return_value=db_set):
            result = await store.aget("db-only")

        assert result is db_set
        # Should also populate cache after DB load
        assert store.get("db-only") is db_set

    async def test_returns_none_when_not_in_cache_or_db(self) -> None:
        store = GeneSetStore()

        with patch.object(store, "_load", new_callable=AsyncMock, return_value=None):
            result = await store.aget("ghost")

        assert result is None


class TestAsyncDelete:
    async def test_removes_from_cache_and_calls_db(self) -> None:
        store = GeneSetStore()
        store.save(_make_set("doomed"))

        with patch.object(store, "_delete_from_db", new_callable=AsyncMock) as mock_del:
            result = await store.adelete("doomed")

        assert result is True
        assert store.get("doomed") is None
        mock_del.assert_awaited_once_with("doomed")


class TestAlistForUser:
    async def test_merges_db_and_cache(self) -> None:
        store = GeneSetStore()
        cached = _make_set("cached", user_id=_USER_A, site_id="plasmo")
        store.save(cached)

        db_only = _make_set("db-only", user_id=_USER_A, site_id="plasmo")

        with patch(
            "veupath_chatbot.services.gene_sets.store._list_from_db",
            new_callable=AsyncMock,
            return_value=[db_only],
        ):
            result = await store.alist_for_user(_USER_A, site_id="plasmo")

        ids = {gs.id for gs in result}
        assert "cached" in ids
        assert "db-only" in ids

    async def test_cache_overrides_db(self) -> None:
        store = GeneSetStore()
        cached_version = _make_set("same-id", user_id=_USER_A, site_id="plasmo")
        cached_version_name = "CACHED VERSION"
        object.__setattr__(cached_version, "name", cached_version_name)
        store.save(cached_version)

        db_version = _make_set("same-id", user_id=_USER_A, site_id="plasmo")

        with patch(
            "veupath_chatbot.services.gene_sets.store._list_from_db",
            new_callable=AsyncMock,
            return_value=[db_version],
        ):
            result = await store.alist_for_user(_USER_A, site_id="plasmo")

        assert len(result) == 1
        assert result[0].name == cached_version_name


class TestAlistAll:
    """Tests for the async alist_all method (merges DB + cache)."""

    async def test_merges_db_and_cache(self) -> None:
        store = GeneSetStore()
        cached = _make_set("cached", site_id="plasmo")
        store.save(cached)

        db_only = _make_set("db-only", site_id="plasmo")

        with patch(
            "veupath_chatbot.services.gene_sets.store._list_from_db",
            new_callable=AsyncMock,
            return_value=[db_only],
        ):
            result = await store.alist_all(site_id="plasmo")

        ids = {gs.id for gs in result}
        assert "cached" in ids
        assert "db-only" in ids

    async def test_filters_by_site(self) -> None:
        store = GeneSetStore()
        store.save(_make_set("plasmo-cached", site_id="plasmo"))
        store.save(_make_set("toxo-cached", site_id="toxo"))

        with patch(
            "veupath_chatbot.services.gene_sets.store._list_from_db",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await store.alist_all(site_id="plasmo")

        assert len(result) == 1
        assert result[0].id == "plasmo-cached"

    async def test_cache_overrides_db(self) -> None:
        store = GeneSetStore()
        cached = _make_set("overlap")
        cached_name = "FROM CACHE"
        object.__setattr__(cached, "name", cached_name)
        store.save(cached)

        db_version = _make_set("overlap")

        with patch(
            "veupath_chatbot.services.gene_sets.store._list_from_db",
            new_callable=AsyncMock,
            return_value=[db_version],
        ):
            result = await store.alist_all()

        assert len(result) == 1
        assert result[0].name == cached_name

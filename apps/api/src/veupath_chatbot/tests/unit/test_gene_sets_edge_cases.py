"""Edge-case tests for gene set store and types."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

from veupath_chatbot.services.gene_sets.store import GeneSetStore
from veupath_chatbot.services.gene_sets.types import GeneSet

_USER_A = uuid4()


def _make_set(
    set_id: str = "gs-1",
    *,
    site_id: str = "plasmo",
    gene_ids: list[str] | None = None,
    user_id: UUID | None = None,
    source: str = "paste",
    name: str | None = None,
) -> GeneSet:
    return GeneSet(
        id=set_id,
        name=name or f"Test Set {set_id}",
        site_id=site_id,
        gene_ids=gene_ids if gene_ids is not None else ["GENE1", "GENE2"],
        source=source,
        user_id=user_id,
        created_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Empty gene list
# ---------------------------------------------------------------------------


class TestEmptyGeneList:
    def test_gene_set_with_empty_genes(self) -> None:
        gs = _make_set(gene_ids=[])
        assert gs.gene_ids == []

    def test_store_saves_empty_gene_set(self) -> None:
        store = GeneSetStore()
        gs = _make_set(gene_ids=[])
        store.save(gs)
        retrieved = store.get("gs-1")
        assert retrieved is not None
        assert retrieved.gene_ids == []


# ---------------------------------------------------------------------------
# Duplicate genes
# ---------------------------------------------------------------------------


class TestDuplicateGenes:
    def test_gene_set_allows_duplicate_ids(self) -> None:
        """GeneSet dataclass does not deduplicate — this is the current behavior."""
        gs = _make_set(gene_ids=["GENE1", "GENE1", "GENE2"])
        assert len(gs.gene_ids) == 3

    def test_store_preserves_duplicates(self) -> None:
        store = GeneSetStore()
        gs = _make_set(gene_ids=["GENE1", "GENE1", "GENE2"])
        store.save(gs)
        retrieved = store.get("gs-1")
        assert retrieved is not None
        assert len(retrieved.gene_ids) == 3


# ---------------------------------------------------------------------------
# Large gene list
# ---------------------------------------------------------------------------


class TestLargeGeneList:
    def test_gene_set_with_large_gene_list(self) -> None:
        gene_ids = [f"GENE_{i:06d}" for i in range(10_000)]
        gs = _make_set(gene_ids=gene_ids)
        assert len(gs.gene_ids) == 10_000

    def test_store_handles_large_gene_set(self) -> None:
        store = GeneSetStore()
        gene_ids = [f"GENE_{i:06d}" for i in range(10_000)]
        gs = _make_set(gene_ids=gene_ids)
        store.save(gs)
        retrieved = store.get("gs-1")
        assert retrieved is not None
        assert len(retrieved.gene_ids) == 10_000


# ---------------------------------------------------------------------------
# Store overflow / many gene sets
# ---------------------------------------------------------------------------


class TestManyGeneSets:
    def test_store_with_many_gene_sets(self) -> None:
        store = GeneSetStore()
        for i in range(500):
            store.save(_make_set(set_id=f"gs-{i}"))
        assert len(store.list_all()) == 500

    def test_list_all_performance_with_site_filter(self) -> None:
        store = GeneSetStore()
        for i in range(200):
            site = "plasmo" if i % 2 == 0 else "toxo"
            store.save(_make_set(set_id=f"gs-{i}", site_id=site))
        plasmo = store.list_all(site_id="plasmo")
        toxo = store.list_all(site_id="toxo")
        assert len(plasmo) == 100
        assert len(toxo) == 100


# ---------------------------------------------------------------------------
# WriteThruStore.adelete bug: always returns True
# ---------------------------------------------------------------------------


class TestAdeleteReturnValue:
    """adelete should return False for non-existent entities,
    consistent with sync delete().
    """

    async def test_adelete_nonexistent_returns_false(self) -> None:
        store = GeneSetStore()
        with patch.object(store, "_delete_from_db", new_callable=AsyncMock):
            result = await store.adelete("nonexistent")
        assert result is False

    async def test_adelete_existing_returns_true(self) -> None:
        store = GeneSetStore()
        store.save(_make_set("doomed"))
        with patch.object(store, "_delete_from_db", new_callable=AsyncMock):
            result = await store.adelete("doomed")
        assert result is True

    async def test_sync_delete_nonexistent_returns_false(self) -> None:
        store = GeneSetStore()
        result = store.delete("nonexistent")
        assert result is False


# ---------------------------------------------------------------------------
# GeneSet dataclass edge cases
# ---------------------------------------------------------------------------


class TestGeneSetDataclass:
    def test_all_optional_fields_none(self) -> None:
        gs = GeneSet(
            id="gs-1",
            name="Test",
            site_id="plasmo",
            gene_ids=["G1"],
            source="paste",
        )
        assert gs.user_id is None
        assert gs.wdk_strategy_id is None
        assert gs.wdk_step_id is None
        assert gs.search_name is None
        assert gs.record_type is None
        assert gs.parameters is None
        assert gs.parent_set_ids == []
        assert gs.operation is None
        assert gs.step_count == 1

    def test_created_at_default(self) -> None:
        before = datetime.now(UTC)
        gs = GeneSet(
            id="gs-1",
            name="Test",
            site_id="plasmo",
            gene_ids=[],
            source="paste",
        )
        after = datetime.now(UTC)
        assert before <= gs.created_at <= after

    def test_gene_set_source_literal(self) -> None:
        """GeneSetSource must be one of the allowed literals."""
        for src in ("strategy", "paste", "upload", "derived", "saved"):
            gs = GeneSet(
                id="gs-1",
                name="Test",
                site_id="plasmo",
                gene_ids=[],
                source=src,
            )
            assert gs.source == src

    def test_derived_gene_set_with_parent_ids(self) -> None:
        gs = GeneSet(
            id="gs-derived",
            name="Intersection Result",
            site_id="plasmo",
            gene_ids=["G1", "G2"],
            source="derived",
            parent_set_ids=["gs-a", "gs-b"],
            operation="intersect",
        )
        assert gs.parent_set_ids == ["gs-a", "gs-b"]
        assert gs.operation == "intersect"


# ---------------------------------------------------------------------------
# Save then delete then get
# ---------------------------------------------------------------------------


class TestSaveDeleteGet:
    def test_save_delete_get_returns_none(self) -> None:
        store = GeneSetStore()
        gs = _make_set("ephemeral")
        store.save(gs)
        assert store.get("ephemeral") is gs
        store.delete("ephemeral")
        assert store.get("ephemeral") is None

    def test_save_overwrite_preserves_latest(self) -> None:
        store = GeneSetStore()
        gs1 = _make_set("shared-id", name="Version 1")
        gs2 = _make_set("shared-id", name="Version 2")
        store.save(gs1)
        store.save(gs2)
        retrieved = store.get("shared-id")
        assert retrieved is not None
        assert retrieved.name == "Version 2"


# ---------------------------------------------------------------------------
# list_for_user with no user_id set on gene sets
# ---------------------------------------------------------------------------


class TestListForUserEdgeCases:
    def test_list_for_user_skips_none_user(self) -> None:
        store = GeneSetStore()
        store.save(_make_set("no-user", user_id=None))
        result = store.list_for_user(_USER_A)
        assert len(result) == 0

    def test_list_for_user_empty_store(self) -> None:
        store = GeneSetStore()
        result = store.list_for_user(_USER_A)
        assert result == []

    def test_list_all_with_none_site_id(self) -> None:
        store = GeneSetStore()
        store.save(_make_set("a", site_id="plasmo"))
        store.save(_make_set("b", site_id="toxo"))
        result = store.list_all(site_id=None)
        assert len(result) == 2

"""Unit tests for strategy-to-gene-set auto-import (TDD Red phase).

The production module ``veupath_chatbot.services.strategies.auto_import``
does not exist yet.  All tests MUST fail with ImportError until implemented.

Eligibility: wdk_strategy_id IS NOT NULL
             AND gene_set_auto_imported IS False
             AND gene_set_id IS NULL
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from veupath_chatbot.persistence.models import StreamProjection
from veupath_chatbot.persistence.repositories.stream import StreamRepository
from veupath_chatbot.services.gene_sets import GeneSet, GeneSetService
from veupath_chatbot.services.strategies.auto_import import auto_import_gene_sets

_USER: UUID = uuid4()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_projection(
    stream_id: UUID | None = None,
    wdk_strategy_id: int | None = None,
    gene_set_id: str | None = None,
    gene_set_auto_imported: bool = False,
    name: str = "Test Strategy",
    site_id: str = "PlasmoDB",
    record_type: str = "transcript",
) -> MagicMock:
    proj = MagicMock(spec=StreamProjection)
    proj.stream_id = stream_id or uuid4()
    proj.wdk_strategy_id = wdk_strategy_id
    proj.gene_set_id = gene_set_id
    proj.gene_set_auto_imported = gene_set_auto_imported
    proj.name = name
    proj.site_id = site_id
    proj.record_type = record_type
    proj.stream = MagicMock()
    proj.stream.user_id = _USER
    proj.stream.site_id = site_id
    return proj


def _make_gene_set(
    name: str = "Test Strategy",
    wdk_strategy_id: int | None = 123,
    site_id: str = "PlasmoDB",
) -> GeneSet:
    return GeneSet(
        id=str(uuid4()),
        name=name,
        site_id=site_id,
        gene_ids=["PF3D7_0000001", "PF3D7_0000002"],
        source="strategy",
        user_id=_USER,
        wdk_strategy_id=wdk_strategy_id,
    )


def _make_stream_repo() -> MagicMock:
    repo = MagicMock(spec=StreamRepository)
    repo.update_projection = AsyncMock()
    return repo


def _make_gene_set_service(gene_set: GeneSet | None = None) -> MagicMock:
    svc = MagicMock(spec=GeneSetService)
    svc.create = AsyncMock(return_value=gene_set or _make_gene_set())
    svc.find_by_wdk_strategy = MagicMock(return_value=None)
    svc.flush = AsyncMock()
    return svc


# ---------------------------------------------------------------------------
# TestAutoImportGeneSet
# ---------------------------------------------------------------------------


class TestAutoImportGeneSet:
    @pytest.mark.asyncio
    async def test_creates_gene_set_for_new_wdk_strategy(self) -> None:
        proj = _make_projection(wdk_strategy_id=123)
        created_gs = _make_gene_set(wdk_strategy_id=123)
        stream_repo = _make_stream_repo()
        gene_set_svc = _make_gene_set_service(gene_set=created_gs)

        result = await auto_import_gene_sets(
            [proj],
            stream_repo=stream_repo,
            gene_set_service=gene_set_svc,
            site_id="PlasmoDB",
            user_id=_USER,
        )

        gene_set_svc.create.assert_called_once()
        assert len(result) == 1
        assert result[0].id == created_gs.id

    @pytest.mark.asyncio
    async def test_skips_strategy_without_wdk_id(self) -> None:
        proj = _make_projection(wdk_strategy_id=None)
        stream_repo = _make_stream_repo()
        gene_set_svc = _make_gene_set_service()

        result = await auto_import_gene_sets(
            [proj],
            stream_repo=stream_repo,
            gene_set_service=gene_set_svc,
            site_id="PlasmoDB",
            user_id=_USER,
        )

        gene_set_svc.create.assert_not_called()
        assert result == []

    @pytest.mark.asyncio
    async def test_skips_already_imported_strategy(self) -> None:
        """gene_set_auto_imported=True blocks re-import even when gene_set_id
        is None (the gene set was deleted)."""
        proj = _make_projection(
            wdk_strategy_id=999,
            gene_set_id=None,
            gene_set_auto_imported=True,
        )
        stream_repo = _make_stream_repo()
        gene_set_svc = _make_gene_set_service()

        result = await auto_import_gene_sets(
            [proj],
            stream_repo=stream_repo,
            gene_set_service=gene_set_svc,
            site_id="PlasmoDB",
            user_id=_USER,
        )

        gene_set_svc.create.assert_not_called()
        assert result == []

    @pytest.mark.asyncio
    async def test_skips_strategy_with_existing_gene_set(self) -> None:
        proj = _make_projection(
            wdk_strategy_id=77,
            gene_set_id=str(uuid4()),
            gene_set_auto_imported=False,
        )
        stream_repo = _make_stream_repo()
        gene_set_svc = _make_gene_set_service()

        result = await auto_import_gene_sets(
            [proj],
            stream_repo=stream_repo,
            gene_set_service=gene_set_svc,
            site_id="PlasmoDB",
            user_id=_USER,
        )

        gene_set_svc.create.assert_not_called()
        assert result == []

    @pytest.mark.asyncio
    async def test_multiple_strategies_batch(self) -> None:
        eligible_1 = _make_projection(wdk_strategy_id=10, name="Strategy A")
        eligible_2 = _make_projection(wdk_strategy_id=20, name="Strategy B")
        no_wdk_id = _make_projection(wdk_strategy_id=None)
        already_imported = _make_projection(
            wdk_strategy_id=30,
            gene_set_auto_imported=True,
        )
        already_linked = _make_projection(
            wdk_strategy_id=40,
            gene_set_id=str(uuid4()),
        )

        gs_a = _make_gene_set(name="Strategy A", wdk_strategy_id=10)
        gs_b = _make_gene_set(name="Strategy B", wdk_strategy_id=20)
        stream_repo = _make_stream_repo()
        gene_set_svc = _make_gene_set_service()
        gene_set_svc.create = AsyncMock(side_effect=[gs_a, gs_b])

        result = await auto_import_gene_sets(
            [eligible_1, eligible_2, no_wdk_id, already_imported, already_linked],
            stream_repo=stream_repo,
            gene_set_service=gene_set_svc,
            site_id="PlasmoDB",
            user_id=_USER,
        )

        assert gene_set_svc.create.call_count == 2
        assert len(result) == 2
        returned_ids = {gs.id for gs in result}
        assert gs_a.id in returned_ids
        assert gs_b.id in returned_ids

    @pytest.mark.asyncio
    async def test_gene_set_has_correct_source(self) -> None:
        proj = _make_projection(wdk_strategy_id=55, site_id="ToxoDB")
        stream_repo = _make_stream_repo()
        gene_set_svc = _make_gene_set_service()

        await auto_import_gene_sets(
            [proj],
            stream_repo=stream_repo,
            gene_set_service=gene_set_svc,
            site_id="ToxoDB",
            user_id=_USER,
        )

        gene_set_svc.create.assert_called_once()
        call_kwargs = gene_set_svc.create.call_args.kwargs
        assert call_kwargs["source"] == "strategy"
        assert call_kwargs["wdk_strategy_id"] == 55

    @pytest.mark.asyncio
    async def test_gene_set_name_matches_strategy(self) -> None:
        proj = _make_projection(wdk_strategy_id=88, name="Kinase Candidates")
        stream_repo = _make_stream_repo()
        gene_set_svc = _make_gene_set_service()

        await auto_import_gene_sets(
            [proj],
            stream_repo=stream_repo,
            gene_set_service=gene_set_svc,
            site_id="PlasmoDB",
            user_id=_USER,
        )

        call_kwargs = gene_set_svc.create.call_args.kwargs
        assert call_kwargs["name"] == "Kinase Candidates"

    @pytest.mark.asyncio
    async def test_idempotent_on_repeated_calls(self) -> None:
        stream_id = uuid4()
        proj_first = _make_projection(stream_id=stream_id, wdk_strategy_id=321)
        created_gs = _make_gene_set(wdk_strategy_id=321)
        stream_repo = _make_stream_repo()
        gene_set_svc = _make_gene_set_service(gene_set=created_gs)

        # First call: eligible
        await auto_import_gene_sets(
            [proj_first],
            stream_repo=stream_repo,
            gene_set_service=gene_set_svc,
            site_id="PlasmoDB",
            user_id=_USER,
        )

        # Simulate the DB state after first import
        proj_second = _make_projection(
            stream_id=stream_id,
            wdk_strategy_id=321,
            gene_set_id=created_gs.id,
            gene_set_auto_imported=True,
        )

        # Second call: must be a no-op
        result_second = await auto_import_gene_sets(
            [proj_second],
            stream_repo=stream_repo,
            gene_set_service=gene_set_svc,
            site_id="PlasmoDB",
            user_id=_USER,
        )

        assert gene_set_svc.create.call_count == 1
        assert result_second == []


# ---------------------------------------------------------------------------
# TestGeneSetDeletion
# ---------------------------------------------------------------------------


class TestGeneSetDeletion:
    @pytest.mark.asyncio
    async def test_delete_gene_set_nullifies_projection_link(self) -> None:
        """After ON DELETE SET NULL, gene_set_id=None but gene_set_auto_imported=True.
        auto_import must not re-create."""
        proj = _make_projection(
            wdk_strategy_id=500,
            gene_set_id=None,
            gene_set_auto_imported=True,
        )
        stream_repo = _make_stream_repo()
        gene_set_svc = _make_gene_set_service()

        result = await auto_import_gene_sets(
            [proj],
            stream_repo=stream_repo,
            gene_set_service=gene_set_svc,
            site_id="PlasmoDB",
            user_id=_USER,
        )

        gene_set_svc.create.assert_not_called()
        assert result == []

    @pytest.mark.asyncio
    async def test_delete_gene_set_does_not_delete_strategy(self) -> None:
        """Projection survives gene-set deletion."""
        stream_id = uuid4()
        proj = _make_projection(
            stream_id=stream_id,
            wdk_strategy_id=600,
            gene_set_id=None,
            gene_set_auto_imported=True,
        )
        stream_repo = _make_stream_repo()
        gene_set_svc = _make_gene_set_service()

        await auto_import_gene_sets(
            [proj],
            stream_repo=stream_repo,
            gene_set_service=gene_set_svc,
            site_id="PlasmoDB",
            user_id=_USER,
        )

        assert proj.stream_id == stream_id

    @pytest.mark.asyncio
    async def test_auto_import_after_gene_set_deletion_does_not_recreate(self) -> None:
        """After gene set deletion + re-sync, no new gene set is created."""
        proj = _make_projection(
            wdk_strategy_id=700,
            gene_set_id=None,
            gene_set_auto_imported=True,
        )
        stream_repo = _make_stream_repo()
        gene_set_svc = _make_gene_set_service()

        result = await auto_import_gene_sets(
            [proj],
            stream_repo=stream_repo,
            gene_set_service=gene_set_svc,
            site_id="PlasmoDB",
            user_id=_USER,
        )

        gene_set_svc.create.assert_not_called()
        stream_repo.update_projection.assert_not_called()
        assert result == []


# ---------------------------------------------------------------------------
# TestStrategyDeletion
# ---------------------------------------------------------------------------


class TestStrategyDeletion:
    @pytest.mark.asyncio
    async def test_delete_strategy_does_not_delete_gene_set(self) -> None:
        """No FK from gene_sets back to streams — deletion of a stream
        does not affect gene sets. When projection list is empty (deleted),
        auto_import is a no-op."""
        stream_repo = _make_stream_repo()
        gene_set_svc = _make_gene_set_service()

        result = await auto_import_gene_sets(
            [],
            stream_repo=stream_repo,
            gene_set_service=gene_set_svc,
            site_id="PlasmoDB",
            user_id=_USER,
        )

        gene_set_svc.create.assert_not_called()
        gene_set_svc.delete.assert_not_called()
        assert result == []

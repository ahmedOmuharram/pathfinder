"""Tests for gene set operations service."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from veupath_chatbot.integrations.veupathdb.wdk_models import WDKAnswer
from veupath_chatbot.platform.errors import (
    InternalError,
    NotFoundError,
    ValidationError,
)
from veupath_chatbot.services.gene_sets.operations import (
    GeneSetService,
    GeneSetWdkContext,
    count_steps_in_tree,
    fetch_gene_ids_from_step,
    resolve_root_step_id,
)
from veupath_chatbot.services.gene_sets.store import GeneSetStore
from veupath_chatbot.services.gene_sets.types import GeneSet

_USER = uuid4()


def _make_set(
    set_id: str = "gs-1",
    *,
    gene_ids: list[str] | None = None,
    user_id: object = None,
    site_id: str = "plasmo",
    wdk: GeneSetWdkContext | None = None,
    name: str = "Test",
) -> GeneSet:
    ctx = wdk or GeneSetWdkContext()
    return GeneSet(
        id=set_id,
        name=name,
        site_id=site_id,
        gene_ids=gene_ids if gene_ids is not None else ["G1", "G2"],
        source="paste",
        user_id=user_id if user_id is not None else _USER,
        wdk_strategy_id=ctx.wdk_strategy_id,
        wdk_step_id=ctx.wdk_step_id,
        search_name=ctx.search_name,
        record_type=ctx.record_type,
        parameters=ctx.parameters,
    )


# ---------------------------------------------------------------------------
# count_steps_in_tree
# ---------------------------------------------------------------------------


class TestCountStepsInTree:
    def test_single_node(self) -> None:
        assert count_steps_in_tree({"id": 1}) == 1

    def test_empty_dict(self) -> None:
        assert count_steps_in_tree({}) == 1

    def test_not_a_dict(self) -> None:
        assert count_steps_in_tree(None) == 0
        assert count_steps_in_tree("junk") == 0
        assert count_steps_in_tree(42) == 0

    def test_linear_chain(self) -> None:
        tree = {
            "id": 3,
            "primaryInput": {
                "id": 2,
                "primaryInput": {"id": 1},
            },
        }
        assert count_steps_in_tree(tree) == 3

    def test_binary_tree(self) -> None:
        tree = {
            "id": 3,
            "primaryInput": {"id": 1},
            "secondaryInput": {"id": 2},
        }
        assert count_steps_in_tree(tree) == 3

    def test_complex_tree(self) -> None:
        tree = {
            "id": 5,
            "primaryInput": {
                "id": 3,
                "primaryInput": {"id": 1},
                "secondaryInput": {"id": 2},
            },
            "secondaryInput": {"id": 4},
        }
        assert count_steps_in_tree(tree) == 5


# ---------------------------------------------------------------------------
# resolve_root_step_id
# ---------------------------------------------------------------------------


class TestResolveRootStepId:
    async def test_returns_root_step_id(self) -> None:
        mock_api = AsyncMock()
        mock_api.get_strategy.return_value = {"rootStepId": 42}

        result = await resolve_root_step_id(mock_api, strategy_id=10)
        assert result == 42
        mock_api.get_strategy.assert_awaited_once_with(10)

    async def test_returns_none_when_missing(self) -> None:
        mock_api = AsyncMock()
        mock_api.get_strategy.return_value = {}

        result = await resolve_root_step_id(mock_api, strategy_id=10)
        assert result is None

    async def test_returns_none_for_non_int(self) -> None:
        mock_api = AsyncMock()
        mock_api.get_strategy.return_value = {"rootStepId": "not-an-int"}

        result = await resolve_root_step_id(mock_api, strategy_id=10)
        assert result is None


# ---------------------------------------------------------------------------
# fetch_gene_ids_from_step
# ---------------------------------------------------------------------------


class TestFetchGeneIdsFromStep:
    async def test_extracts_gene_ids(self) -> None:
        mock_api = AsyncMock()
        mock_api.get_step_answer.return_value = WDKAnswer.model_validate({
            "records": [
                {"id": [{"name": "source_id", "value": "GENE1"}]},
                {"id": [{"name": "source_id", "value": "GENE2"}]},
            ],
            "meta": {"totalCount": 2},
        })

        result = await fetch_gene_ids_from_step(mock_api, step_id=99)
        assert result == ["GENE1", "GENE2"]

    async def test_empty_records(self) -> None:
        mock_api = AsyncMock()
        mock_api.get_step_answer.return_value = WDKAnswer.model_validate({
            "records": [],
            "meta": {"totalCount": 0},
        })

        result = await fetch_gene_ids_from_step(mock_api, step_id=99)
        assert result == []

    async def test_missing_records_defaults_empty(self) -> None:
        """WDKAnswer defaults records to [] when key is absent."""
        mock_api = AsyncMock()
        mock_api.get_step_answer.return_value = WDKAnswer.model_validate({
            "meta": {"totalCount": 0},
        })

        result = await fetch_gene_ids_from_step(mock_api, step_id=99)
        assert result == []


# ---------------------------------------------------------------------------
# GeneSetService.get_for_user
# ---------------------------------------------------------------------------


class TestGetForUser:
    async def test_returns_gene_set(self) -> None:
        store = GeneSetStore()
        gs = _make_set()
        store.save(gs)
        svc = GeneSetService(store)

        result = await svc.get_for_user(_USER, "gs-1")
        assert result.id == "gs-1"

    async def test_raises_for_wrong_user(self) -> None:
        store = GeneSetStore()
        gs = _make_set()
        store.save(gs)
        svc = GeneSetService(store)

        other_user = uuid4()
        with pytest.raises(NotFoundError):
            await svc.get_for_user(other_user, "gs-1")

    async def test_raises_for_missing(self) -> None:
        store = GeneSetStore()
        svc = GeneSetService(store)

        with (
            patch.object(store, "_load", new_callable=AsyncMock, return_value=None),
            pytest.raises(NotFoundError),
        ):
            await svc.get_for_user(_USER, "nonexistent")


# ---------------------------------------------------------------------------
# GeneSetService.perform_set_operation
# ---------------------------------------------------------------------------


class TestPerformSetOperation:
    def _svc_with_sets(self, gs_a: GeneSet, gs_b: GeneSet) -> GeneSetService:
        store = GeneSetStore()
        store.save(gs_a)
        store.save(gs_b)
        return GeneSetService(store)

    async def test_union(self) -> None:
        a = _make_set("a", gene_ids=["G1", "G2"])
        b = _make_set("b", gene_ids=["G2", "G3"])
        svc = self._svc_with_sets(a, b)

        result = await svc.perform_set_operation(
            user_id=_USER,
            set_a_id="a",
            set_b_id="b",
            operation="union",
            name="Union",
        )
        assert sorted(result.gene_ids) == ["G1", "G2", "G3"]
        assert result.source == "derived"
        assert result.operation == "union"
        assert result.parent_set_ids == ["a", "b"]

    async def test_intersect(self) -> None:
        a = _make_set("a", gene_ids=["G1", "G2", "G3"])
        b = _make_set("b", gene_ids=["G2", "G3", "G4"])
        svc = self._svc_with_sets(a, b)

        result = await svc.perform_set_operation(
            user_id=_USER,
            set_a_id="a",
            set_b_id="b",
            operation="intersect",
            name="Intersection",
        )
        assert sorted(result.gene_ids) == ["G2", "G3"]

    async def test_minus(self) -> None:
        a = _make_set("a", gene_ids=["G1", "G2", "G3"])
        b = _make_set("b", gene_ids=["G2"])
        svc = self._svc_with_sets(a, b)

        result = await svc.perform_set_operation(
            user_id=_USER,
            set_a_id="a",
            set_b_id="b",
            operation="minus",
            name="Minus",
        )
        assert sorted(result.gene_ids) == ["G1", "G3"]

    async def test_invalid_operation_raises(self) -> None:
        a = _make_set("a")
        b = _make_set("b")
        svc = self._svc_with_sets(a, b)

        with pytest.raises(ValidationError, match="Invalid operation"):
            await svc.perform_set_operation(
                user_id=_USER,
                set_a_id="a",
                set_b_id="b",
                operation="xor",
                name="Bad",
            )

    async def test_persists_to_store(self) -> None:
        a = _make_set("a", gene_ids=["G1"])
        b = _make_set("b", gene_ids=["G2"])
        store = GeneSetStore()
        store.save(a)
        store.save(b)
        svc = GeneSetService(store)

        result = await svc.perform_set_operation(
            user_id=_USER,
            set_a_id="a",
            set_b_id="b",
            operation="union",
            name="Saved",
        )
        assert store.get(result.id) is not None


# ---------------------------------------------------------------------------
# GeneSetService.create
# ---------------------------------------------------------------------------


class TestCreate:
    async def test_create_from_gene_ids(self) -> None:
        store = GeneSetStore()
        svc = GeneSetService(store)

        result = await svc.create(
            user_id=_USER,
            name="My Set",
            site_id="plasmo",
            gene_ids=["G1", "G2"],
            source="paste",
        )
        assert result.name == "My Set"
        assert result.gene_ids == ["G1", "G2"]
        assert result.source == "paste"
        assert store.get(result.id) is not None

    @patch("veupath_chatbot.services.gene_sets.operations.get_strategy_api")
    async def test_create_from_strategy_auto_resolves(
        self, mock_get_api: MagicMock
    ) -> None:
        mock_api = AsyncMock()
        mock_get_api.return_value = mock_api
        # get_strategy called twice: once for resolve_root_step_id, once for step count
        mock_api.get_strategy.return_value = {
            "rootStepId": 42,
            "stepTree": {
                "id": 42,
                "primaryInput": {"id": 41},
            },
        }
        mock_api.get_step_answer.return_value = WDKAnswer.model_validate({
            "records": [
                {"id": [{"name": "source_id", "value": "RESOLVED_G1"}]},
            ],
            "meta": {"totalCount": 1},
        })

        store = GeneSetStore()
        svc = GeneSetService(store)

        result = await svc.create(
            user_id=_USER,
            name="From Strategy",
            site_id="plasmo",
            gene_ids=[],
            source="strategy",
            wdk=GeneSetWdkContext(wdk_strategy_id=100),
        )
        assert result.wdk_step_id == 42
        assert result.gene_ids == ["RESOLVED_G1"]
        assert result.step_count == 2

    async def test_create_with_explicit_gene_ids_skips_resolution(self) -> None:
        store = GeneSetStore()
        svc = GeneSetService(store)

        result = await svc.create(
            user_id=_USER,
            name="Explicit",
            site_id="plasmo",
            gene_ids=["G1"],
            source="paste",
            wdk=GeneSetWdkContext(wdk_strategy_id=100),
        )
        # Should not attempt resolution since gene_ids are provided
        assert result.gene_ids == ["G1"]


# ---------------------------------------------------------------------------
# GeneSetService.delete
# ---------------------------------------------------------------------------


class TestDelete:
    async def test_delete_existing(self) -> None:
        store = GeneSetStore()
        store.save(_make_set("doomed"))
        svc = GeneSetService(store)

        await svc.delete(_USER, "doomed")
        assert store.get("doomed") is None

    async def test_delete_nonexistent_raises(self) -> None:
        store = GeneSetStore()
        svc = GeneSetService(store)

        with (
            patch.object(store, "_load", new_callable=AsyncMock, return_value=None),
            pytest.raises(NotFoundError),
        ):
            await svc.delete(_USER, "ghost")

    async def test_delete_wrong_user_raises(self) -> None:
        store = GeneSetStore()
        store.save(_make_set("owned"))
        svc = GeneSetService(store)

        with pytest.raises(NotFoundError):
            await svc.delete(uuid4(), "owned")


# ---------------------------------------------------------------------------
# GeneSetService.list_for_user
# ---------------------------------------------------------------------------


class TestListForUser:
    async def test_returns_user_sets(self) -> None:
        store = GeneSetStore()
        store.save(_make_set("a", user_id=_USER))
        store.save(_make_set("b", user_id=uuid4()))
        svc = GeneSetService(store)

        with patch(
            "veupath_chatbot.services.gene_sets.store._list_from_db",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await svc.list_for_user(_USER)
        assert len(result) == 1
        assert result[0].id == "a"

    async def test_filters_by_site(self) -> None:
        store = GeneSetStore()
        store.save(_make_set("a", user_id=_USER, site_id="plasmo"))
        store.save(_make_set("b", user_id=_USER, site_id="toxo"))
        svc = GeneSetService(store)

        with patch(
            "veupath_chatbot.services.gene_sets.store._list_from_db",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await svc.list_for_user(_USER, site_id="plasmo")
        assert len(result) == 1
        assert result[0].id == "a"


# ---------------------------------------------------------------------------
# GeneSetService.get_step_results_service
# ---------------------------------------------------------------------------


class TestGetStepResultsService:
    @patch("veupath_chatbot.services.gene_sets.operations.get_strategy_api")
    async def test_returns_service(self, mock_get_api: MagicMock) -> None:
        mock_api = MagicMock()
        mock_get_api.return_value = mock_api

        store = GeneSetStore()
        gs = _make_set(
            wdk=GeneSetWdkContext(wdk_step_id=42, record_type="gene"),
        )
        store.save(gs)
        svc = GeneSetService(store)

        step_svc = await svc.get_step_results_service(_USER, "gs-1")
        assert step_svc._step_id == 42
        assert step_svc._record_type == "gene"

    async def test_raises_when_no_wdk_step(self) -> None:
        store = GeneSetStore()
        gs = _make_set(wdk=GeneSetWdkContext(wdk_step_id=None))
        store.save(gs)
        svc = GeneSetService(store)

        with pytest.raises(ValidationError, match="No WDK strategy"):
            await svc.get_step_results_service(_USER, "gs-1")


# ---------------------------------------------------------------------------
# GeneSetService.run_enrichment
# ---------------------------------------------------------------------------


class TestRunEnrichment:
    @patch("veupath_chatbot.services.gene_sets.operations.EnrichmentService")
    async def test_calls_enrichment_service(self, mock_cls: MagicMock) -> None:
        mock_svc = AsyncMock()
        mock_cls.return_value = mock_svc
        mock_result = MagicMock()
        mock_svc.run_batch.return_value = ([mock_result], [])

        store = GeneSetStore()
        gs = _make_set(
            wdk=GeneSetWdkContext(
                wdk_step_id=42,
                search_name="GenesByKeyword",
                record_type="gene",
                parameters={"keyword": "kinase"},
            ),
        )
        store.save(gs)
        svc = GeneSetService(store)

        results = await svc.run_enrichment(_USER, "gs-1", ["go_enrichment"])
        assert results == [mock_result]

    @patch("veupath_chatbot.services.gene_sets.operations.EnrichmentService")
    async def test_raises_on_total_failure(self, mock_cls: MagicMock) -> None:
        mock_svc = AsyncMock()
        mock_cls.return_value = mock_svc
        mock_svc.run_batch.return_value = ([], ["go_enrichment: failed"])

        store = GeneSetStore()
        gs = _make_set(wdk=GeneSetWdkContext(wdk_step_id=42))
        store.save(gs)
        svc = GeneSetService(store)

        with pytest.raises(InternalError, match="Enrichment analysis failed"):
            await svc.run_enrichment(_USER, "gs-1", ["go_enrichment"])

"""Tests for WorkbenchToolsMixin — verifying async store usage."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

from veupath_chatbot.ai.tools.planner.workbench_tools import (
    WdkSourceSpec,
    WorkbenchToolsMixin,
)
from veupath_chatbot.services.gene_sets.store import GeneSetStore
from veupath_chatbot.services.gene_sets.types import GeneSet

_USER_ID = uuid4()
_SITE_ID = "plasmodb"


def _make_gene_set(gs_id: str = "gs-1", **kwargs: object) -> GeneSet:
    defaults: dict[str, object] = {
        "id": gs_id,
        "name": "Test Set",
        "site_id": _SITE_ID,
        "gene_ids": ["PF3D7_0100100", "PF3D7_0831900"],
        "source": "strategy",
        "user_id": _USER_ID,
        "wdk_step_id": 42,
        "search_name": "GenesByTextSearch",
        "record_type": "gene",
        "parameters": {"text_expression": "kinase"},
    }
    defaults.update(kwargs)
    return GeneSet(**defaults)


class _TestableTools(WorkbenchToolsMixin):
    """Concrete subclass of WorkbenchToolsMixin for testing."""

    def __init__(self, site_id: str = _SITE_ID, user_id: object = _USER_ID) -> None:
        self.site_id = site_id
        self.user_id = user_id


class TestCreateGeneSet:
    async def test_creates_and_returns_summary(self) -> None:
        tools = _TestableTools()
        store = GeneSetStore()

        with patch(
            "veupath_chatbot.ai.tools.planner.workbench_tools.get_gene_set_store",
            return_value=store,
        ):
            result = await tools.create_workbench_gene_set(
                name="Kinases",
                gene_ids=["PF3D7_0100100"],
            )

        assert result["geneSetCreated"]["name"] == "Kinases"
        assert result["geneSetCreated"]["geneCount"] == 1
        assert result["geneSetCreated"]["source"] == "paste"
        # Verify it was saved to the store
        gs_id = result["geneSetCreated"]["id"]
        assert store.get(gs_id) is not None

    async def test_sets_strategy_source_when_wdk_strategy_provided(self) -> None:
        tools = _TestableTools()
        store = GeneSetStore()

        with patch(
            "veupath_chatbot.ai.tools.planner.workbench_tools.get_gene_set_store",
            return_value=store,
        ):
            result = await tools.create_workbench_gene_set(
                name="From Strategy",
                gene_ids=["PF3D7_0100100"],
                wdk_source=WdkSourceSpec(wdk_strategy_id=99),
            )

        assert result["geneSetCreated"]["source"] == "strategy"

    async def test_default_record_type_is_gene(self) -> None:
        tools = _TestableTools()
        store = GeneSetStore()

        with patch(
            "veupath_chatbot.ai.tools.planner.workbench_tools.get_gene_set_store",
            return_value=store,
        ):
            result = await tools.create_workbench_gene_set(
                name="Defaults",
                gene_ids=["PF3D7_0100100"],
            )

        gs_id = result["geneSetCreated"]["id"]
        gs = store.get(gs_id)
        assert gs is not None
        assert gs.record_type == "transcript"

    async def test_site_id_propagated_to_gene_set(self) -> None:
        tools = _TestableTools(site_id="toxodb")
        store = GeneSetStore()

        with patch(
            "veupath_chatbot.ai.tools.planner.workbench_tools.get_gene_set_store",
            return_value=store,
        ):
            result = await tools.create_workbench_gene_set(
                name="Toxo Genes",
                gene_ids=["TGME49_200010"],
            )

        assert result["geneSetCreated"]["siteId"] == "toxodb"
        gs_id = result["geneSetCreated"]["id"]
        gs = store.get(gs_id)
        assert gs is not None
        assert gs.site_id == "toxodb"

    async def test_message_field_includes_name_and_count(self) -> None:
        tools = _TestableTools()
        store = GeneSetStore()

        with patch(
            "veupath_chatbot.ai.tools.planner.workbench_tools.get_gene_set_store",
            return_value=store,
        ):
            result = await tools.create_workbench_gene_set(
                name="Kinases",
                gene_ids=["PF3D7_0100100", "PF3D7_0200200"],
            )

        assert "Kinases" in result["message"]
        assert "2 genes" in result["message"]

    async def test_search_params_stored_on_gene_set(self) -> None:
        tools = _TestableTools()
        store = GeneSetStore()

        with patch(
            "veupath_chatbot.ai.tools.planner.workbench_tools.get_gene_set_store",
            return_value=store,
        ):
            result = await tools.create_workbench_gene_set(
                name="With Params",
                gene_ids=["PF3D7_0100100"],
                wdk_source=WdkSourceSpec(
                    search_name="GenesByFoldChange",
                    parameters={"fold_change": "2.0"},
                    wdk_step_id=42,
                ),
            )

        gs_id = result["geneSetCreated"]["id"]
        gs = store.get(gs_id)
        assert gs is not None
        assert gs.search_name == "GenesByFoldChange"
        assert gs.parameters == {"fold_change": "2.0"}
        assert gs.wdk_step_id == 42


class TestRunGeneSetEnrichment:
    async def test_uses_async_store_get(self) -> None:
        """Bug fix: run_gene_set_enrichment must use await store.aget()
        so it finds gene sets persisted to DB but not in cache."""
        tools = _TestableTools()
        gs = _make_gene_set("db-only")

        store = GeneSetStore()
        # Gene set is NOT in cache — only available via async DB fallback
        assert store.get("db-only") is None

        mock_aget = AsyncMock(return_value=gs)

        with (
            patch(
                "veupath_chatbot.ai.tools.planner.workbench_tools.get_gene_set_store",
                return_value=store,
            ),
            patch.object(store, "aget", mock_aget),
            patch(
                "veupath_chatbot.services.wdk.enrichment_service.EnrichmentService.run_batch",
                new_callable=AsyncMock,
                return_value=([], []),
            ),
        ):
            result = await tools.run_gene_set_enrichment(gene_set_id="db-only")

        # Should NOT return an error — the gene set should have been found via aget
        assert "error" not in result
        assert result["geneSetId"] == "db-only"
        mock_aget.assert_awaited_once_with("db-only")

    async def test_default_enrichment_types_are_all_five(self) -> None:
        tools = _TestableTools()
        gs = _make_gene_set("gs-types")

        store = GeneSetStore()
        mock_aget = AsyncMock(return_value=gs)

        with (
            patch(
                "veupath_chatbot.ai.tools.planner.workbench_tools.get_gene_set_store",
                return_value=store,
            ),
            patch.object(store, "aget", mock_aget),
            patch(
                "veupath_chatbot.services.wdk.enrichment_service.EnrichmentService.run_batch",
                new_callable=AsyncMock,
                return_value=([], []),
            ) as mock_batch,
        ):
            await tools.run_gene_set_enrichment(gene_set_id="gs-types")

        call_kwargs = mock_batch.call_args.kwargs
        assert call_kwargs["analysis_types"] == [
            "go_function",
            "go_process",
            "go_component",
            "pathway",
            "word",
        ]

    async def test_custom_enrichment_types(self) -> None:
        tools = _TestableTools()
        gs = _make_gene_set("gs-custom")

        store = GeneSetStore()
        mock_aget = AsyncMock(return_value=gs)

        with (
            patch(
                "veupath_chatbot.ai.tools.planner.workbench_tools.get_gene_set_store",
                return_value=store,
            ),
            patch.object(store, "aget", mock_aget),
            patch(
                "veupath_chatbot.services.wdk.enrichment_service.EnrichmentService.run_batch",
                new_callable=AsyncMock,
                return_value=([], []),
            ) as mock_batch,
        ):
            await tools.run_gene_set_enrichment(
                gene_set_id="gs-custom",
                enrichment_types=["go_function", "pathway"],
            )

        call_kwargs = mock_batch.call_args.kwargs
        assert call_kwargs["analysis_types"] == ["go_function", "pathway"]

    async def test_enrichment_counts_significant_terms(self) -> None:
        """Verify totalSignificantTerms counts terms with pValue < 0.05."""
        tools = _TestableTools()
        gs = _make_gene_set("gs-sig")

        store = GeneSetStore()
        mock_aget = AsyncMock(return_value=gs)

        # run_enrichment_for_gene_set now returns a complete summary dict.
        # Mock it at the import site in the workbench_tools module.
        mock_summary = {
            "analysisTypesRun": ["go_function", "go_process"],
            "totalSignificantTerms": 2,
            "enrichmentResults": [
                {
                    "analysisType": "go_function",
                    "terms": [
                        {"term": "kinase", "pValue": 0.001},
                        {"term": "binding", "pValue": 0.10},
                    ],
                },
                {
                    "analysisType": "go_process",
                    "terms": [
                        {"term": "phosphorylation", "pValue": 0.02},
                    ],
                },
            ],
        }

        with (
            patch(
                "veupath_chatbot.ai.tools.planner.workbench_tools.get_gene_set_store",
                return_value=store,
            ),
            patch.object(store, "aget", mock_aget),
            patch(
                "veupath_chatbot.ai.tools.planner.workbench_tools.run_enrichment_for_gene_set",
                new_callable=AsyncMock,
                return_value=mock_summary,
            ),
        ):
            result = await tools.run_gene_set_enrichment(gene_set_id="gs-sig")

        # kinase (0.001) + phosphorylation (0.02) = 2 significant; binding (0.10) is not
        assert result["totalSignificantTerms"] == 2
        assert result["analysisTypesRun"] == ["go_function", "go_process"]

    async def test_enrichment_includes_errors(self) -> None:
        tools = _TestableTools()
        gs = _make_gene_set("gs-err")

        store = GeneSetStore()
        mock_aget = AsyncMock(return_value=gs)

        with (
            patch(
                "veupath_chatbot.ai.tools.planner.workbench_tools.get_gene_set_store",
                return_value=store,
            ),
            patch.object(store, "aget", mock_aget),
            patch(
                "veupath_chatbot.services.wdk.enrichment_service.EnrichmentService.run_batch",
                new_callable=AsyncMock,
                return_value=([], ["go_function failed: timeout"]),
            ),
        ):
            result = await tools.run_gene_set_enrichment(gene_set_id="gs-err")

        assert result["errors"] == ["go_function failed: timeout"]

    async def test_enrichment_no_errors_key_when_empty(self) -> None:
        tools = _TestableTools()
        gs = _make_gene_set("gs-ok")

        store = GeneSetStore()
        mock_aget = AsyncMock(return_value=gs)

        with (
            patch(
                "veupath_chatbot.ai.tools.planner.workbench_tools.get_gene_set_store",
                return_value=store,
            ),
            patch.object(store, "aget", mock_aget),
            patch(
                "veupath_chatbot.services.wdk.enrichment_service.EnrichmentService.run_batch",
                new_callable=AsyncMock,
                return_value=([], []),
            ),
        ):
            result = await tools.run_gene_set_enrichment(gene_set_id="gs-ok")

        assert "errors" not in result

    async def test_returns_error_when_gene_set_not_found(self) -> None:
        tools = _TestableTools()
        store = GeneSetStore()

        mock_aget = AsyncMock(return_value=None)

        with (
            patch(
                "veupath_chatbot.ai.tools.planner.workbench_tools.get_gene_set_store",
                return_value=store,
            ),
            patch.object(store, "aget", mock_aget),
            patch.object(store, "alist_for_user", AsyncMock(return_value=[])),
        ):
            result = await tools.run_gene_set_enrichment(gene_set_id="nonexistent")

        assert "error" in result


class TestListWorkbenchGeneSets:
    async def test_uses_async_list_for_user(self) -> None:
        """Bug fix: list_workbench_gene_sets must use await store.alist_for_user()
        so it finds gene sets persisted to DB but not in cache."""
        tools = _TestableTools(user_id=_USER_ID)
        gs = _make_gene_set("db-only")

        store = GeneSetStore()
        mock_alist = AsyncMock(return_value=[gs])

        with (
            patch(
                "veupath_chatbot.ai.tools.planner.workbench_tools.get_gene_set_store",
                return_value=store,
            ),
            patch.object(store, "alist_for_user", mock_alist),
        ):
            result = await tools.list_workbench_gene_sets()

        assert result["totalSets"] == 1
        assert result["geneSets"][0]["id"] == "db-only"
        mock_alist.assert_awaited_once_with(_USER_ID, site_id=_SITE_ID)

    async def test_uses_async_list_all_when_no_user(self) -> None:
        """Bug fix: when user_id is None, should use await store.alist_all()."""
        tools = _TestableTools(user_id=None)
        gs = _make_gene_set("anon")

        store = GeneSetStore()
        mock_alist_all = AsyncMock(return_value=[gs])

        with (
            patch(
                "veupath_chatbot.ai.tools.planner.workbench_tools.get_gene_set_store",
                return_value=store,
            ),
            patch.object(store, "alist_all", mock_alist_all),
        ):
            result = await tools.list_workbench_gene_sets()

        assert result["totalSets"] == 1
        mock_alist_all.assert_awaited_once_with(site_id=_SITE_ID)

    async def test_returns_gene_set_summary_fields(self) -> None:
        tools = _TestableTools()
        gs = _make_gene_set("gs-1")

        store = GeneSetStore()
        mock_alist = AsyncMock(return_value=[gs])

        with (
            patch(
                "veupath_chatbot.ai.tools.planner.workbench_tools.get_gene_set_store",
                return_value=store,
            ),
            patch.object(store, "alist_for_user", mock_alist),
        ):
            result = await tools.list_workbench_gene_sets()

        entry = result["geneSets"][0]
        assert entry["id"] == "gs-1"
        assert entry["name"] == "Test Set"
        assert entry["geneCount"] == 2
        assert entry["source"] == "strategy"
        assert entry["searchName"] == "GenesByTextSearch"
        assert entry["hasWdkStep"] is True

    async def test_has_wdk_step_false_when_no_step_id(self) -> None:
        tools = _TestableTools()
        gs = _make_gene_set("gs-no-step", wdk_step_id=None)

        store = GeneSetStore()
        mock_alist = AsyncMock(return_value=[gs])

        with (
            patch(
                "veupath_chatbot.ai.tools.planner.workbench_tools.get_gene_set_store",
                return_value=store,
            ),
            patch.object(store, "alist_for_user", mock_alist),
        ):
            result = await tools.list_workbench_gene_sets()

        entry = result["geneSets"][0]
        assert entry["hasWdkStep"] is False

    async def test_empty_list_returns_zero_total(self) -> None:
        tools = _TestableTools()

        store = GeneSetStore()
        mock_alist = AsyncMock(return_value=[])

        with (
            patch(
                "veupath_chatbot.ai.tools.planner.workbench_tools.get_gene_set_store",
                return_value=store,
            ),
            patch.object(store, "alist_for_user", mock_alist),
        ):
            result = await tools.list_workbench_gene_sets()

        assert result["geneSets"] == []
        assert result["totalSets"] == 0

"""Tests for GeneToolsMixin — gene lookup and ID resolution."""

from unittest.mock import AsyncMock, patch

from veupath_chatbot.ai.tools.planner.gene_tools import GeneToolsMixin
from veupath_chatbot.services.gene_lookup.lookup import GeneSearchResult
from veupath_chatbot.services.gene_lookup.result import GeneResult
from veupath_chatbot.services.gene_lookup.wdk import GeneResolveResult

_SITE_ID = "plasmodb"


class _TestableTools(GeneToolsMixin):
    """Concrete subclass for testing."""

    def __init__(self, site_id: str = _SITE_ID) -> None:
        self.site_id = site_id


class TestLookupGeneRecords:
    async def test_delegates_to_lookup_genes_by_text(self) -> None:
        tools = _TestableTools()
        expected = GeneSearchResult(
            records=[GeneResult(gene_id="PF3D7_0100100")], total_count=1
        )

        with patch(
            "veupath_chatbot.ai.tools.planner.gene_tools.lookup_genes_by_text",
            new_callable=AsyncMock,
            return_value=expected,
        ) as mock_lookup:
            result = await tools.lookup_gene_records(query="kinase")

        assert result == expected
        mock_lookup.assert_awaited_once_with(
            _SITE_ID,
            "kinase",
            organism=None,
            limit=10,
        )

    async def test_passes_organism_filter(self) -> None:
        tools = _TestableTools()
        expected = GeneSearchResult(records=[], total_count=0)

        with patch(
            "veupath_chatbot.ai.tools.planner.gene_tools.lookup_genes_by_text",
            new_callable=AsyncMock,
            return_value=expected,
        ) as mock_lookup:
            await tools.lookup_gene_records(query="ap2", organism="P. falciparum")

        mock_lookup.assert_awaited_once_with(
            _SITE_ID,
            "ap2",
            organism="P. falciparum",
            limit=10,
        )

    async def test_limit_clamped_to_minimum_1(self) -> None:
        tools = _TestableTools()
        expected = GeneSearchResult(records=[], total_count=0)

        with patch(
            "veupath_chatbot.ai.tools.planner.gene_tools.lookup_genes_by_text",
            new_callable=AsyncMock,
            return_value=expected,
        ) as mock_lookup:
            await tools.lookup_gene_records(query="test", limit=0)

        # max(1, min(0, 50)) = max(1, 0) = 1
        mock_lookup.assert_awaited_once_with(
            _SITE_ID,
            "test",
            organism=None,
            limit=1,
        )

    async def test_limit_clamped_to_negative_becomes_1(self) -> None:
        tools = _TestableTools()
        expected = GeneSearchResult(records=[], total_count=0)

        with patch(
            "veupath_chatbot.ai.tools.planner.gene_tools.lookup_genes_by_text",
            new_callable=AsyncMock,
            return_value=expected,
        ) as mock_lookup:
            await tools.lookup_gene_records(query="test", limit=-5)

        mock_lookup.assert_awaited_once_with(
            _SITE_ID,
            "test",
            organism=None,
            limit=1,
        )

    async def test_limit_clamped_to_maximum_50(self) -> None:
        tools = _TestableTools()
        expected = GeneSearchResult(records=[], total_count=0)

        with patch(
            "veupath_chatbot.ai.tools.planner.gene_tools.lookup_genes_by_text",
            new_callable=AsyncMock,
            return_value=expected,
        ) as mock_lookup:
            await tools.lookup_gene_records(query="test", limit=100)

        # max(1, min(100, 50)) = max(1, 50) = 50
        mock_lookup.assert_awaited_once_with(
            _SITE_ID,
            "test",
            organism=None,
            limit=50,
        )

    async def test_limit_within_range_passes_through(self) -> None:
        tools = _TestableTools()
        expected = GeneSearchResult(records=[], total_count=0)

        with patch(
            "veupath_chatbot.ai.tools.planner.gene_tools.lookup_genes_by_text",
            new_callable=AsyncMock,
            return_value=expected,
        ) as mock_lookup:
            await tools.lookup_gene_records(query="test", limit=25)

        mock_lookup.assert_awaited_once_with(
            _SITE_ID,
            "test",
            organism=None,
            limit=25,
        )


class TestResolveGeneIdsToRecords:
    async def test_delegates_to_resolve_gene_ids(self) -> None:
        tools = _TestableTools()
        expected = GeneResolveResult(
            records=[GeneResult(gene_id="PF3D7_0100100", product="kinase")],
            total_count=1,
        )

        with patch(
            "veupath_chatbot.ai.tools.planner.gene_tools.resolve_gene_ids",
            new_callable=AsyncMock,
            return_value=expected,
        ) as mock_resolve:
            result = await tools.resolve_gene_ids_to_records(gene_ids=["PF3D7_0100100"])

        assert result == expected
        mock_resolve.assert_awaited_once_with(
            _SITE_ID,
            ["PF3D7_0100100"],
            record_type="transcript",
            search_name="GeneByLocusTag",
            param_name="ds_gene_ids",
        )

    async def test_passes_custom_params(self) -> None:
        tools = _TestableTools()
        expected = GeneResolveResult(records=[], total_count=0)

        with patch(
            "veupath_chatbot.ai.tools.planner.gene_tools.resolve_gene_ids",
            new_callable=AsyncMock,
            return_value=expected,
        ) as mock_resolve:
            await tools.resolve_gene_ids_to_records(
                gene_ids=["g1"],
                record_type="gene",
                search_name="CustomSearch",
                param_name="custom_param",
            )

        mock_resolve.assert_awaited_once_with(
            _SITE_ID,
            ["g1"],
            record_type="gene",
            search_name="CustomSearch",
            param_name="custom_param",
        )

    async def test_empty_list_returns_error(self) -> None:
        tools = _TestableTools()
        result = await tools.resolve_gene_ids_to_records(gene_ids=[])
        assert result == GeneResolveResult(
            records=[], total_count=0, error="No gene IDs provided."
        )

    async def test_whitespace_only_ids_treated_as_empty(self) -> None:
        tools = _TestableTools()
        result = await tools.resolve_gene_ids_to_records(gene_ids=["  ", "", "\t"])
        assert result == GeneResolveResult(
            records=[], total_count=0, error="No gene IDs provided."
        )

    async def test_strips_whitespace_from_ids(self) -> None:
        tools = _TestableTools()
        expected = GeneResolveResult(records=[], total_count=0)

        with patch(
            "veupath_chatbot.ai.tools.planner.gene_tools.resolve_gene_ids",
            new_callable=AsyncMock,
            return_value=expected,
        ) as mock_resolve:
            await tools.resolve_gene_ids_to_records(
                gene_ids=["  PF3D7_0100100  ", "PF3D7_0200200"]
            )

        mock_resolve.assert_awaited_once_with(
            _SITE_ID,
            ["PF3D7_0100100", "PF3D7_0200200"],
            record_type="transcript",
            search_name="GeneByLocusTag",
            param_name="ds_gene_ids",
        )

    async def test_too_many_ids_returns_error(self) -> None:
        tools = _TestableTools()
        ids = [f"GENE_{i}" for i in range(201)]
        result = await tools.resolve_gene_ids_to_records(gene_ids=ids)
        assert result == GeneResolveResult(
            records=[],
            total_count=0,
            error="Too many IDs (max 200). Reduce the list.",
        )

    async def test_exactly_200_ids_is_allowed(self) -> None:
        tools = _TestableTools()
        ids = [f"GENE_{i}" for i in range(200)]
        expected = GeneResolveResult(records=[], total_count=0)

        with patch(
            "veupath_chatbot.ai.tools.planner.gene_tools.resolve_gene_ids",
            new_callable=AsyncMock,
            return_value=expected,
        ) as mock_resolve:
            result = await tools.resolve_gene_ids_to_records(gene_ids=ids)

        assert result.error is None
        mock_resolve.assert_awaited_once()

    async def test_filters_blank_then_checks_count(self) -> None:
        """If after stripping whitespace, remaining IDs are under 200, it should pass."""
        tools = _TestableTools()
        # 201 entries but many are blank
        ids = [f"GENE_{i}" for i in range(100)] + [""] * 101
        expected = GeneResolveResult(records=[], total_count=0)

        with patch(
            "veupath_chatbot.ai.tools.planner.gene_tools.resolve_gene_ids",
            new_callable=AsyncMock,
            return_value=expected,
        ):
            result = await tools.resolve_gene_ids_to_records(gene_ids=ids)

        assert result.error is None

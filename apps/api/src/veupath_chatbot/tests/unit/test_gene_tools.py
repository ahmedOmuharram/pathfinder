"""Tests for GeneToolsMixin -- gene lookup and ID resolution.

Mocks: lookup_genes_by_text and resolve_gene_ids service functions are mocked.
Tests validate delegation, parameter clamping, and whitespace handling, not
WDK integration.
"""

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
        ):
            result = await tools.lookup_gene_records(query="kinase")

        assert result == expected


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
        ):
            result = await tools.resolve_gene_ids_to_records(gene_ids=["PF3D7_0100100"])

        assert result == expected

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
        ):
            result = await tools.resolve_gene_ids_to_records(gene_ids=ids)

        assert result.error is None

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

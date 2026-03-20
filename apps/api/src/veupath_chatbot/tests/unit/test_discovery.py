"""Unit tests for the discovery service module.

Covers SearchCatalog loading (expanded / non-expanded record types,
dict/list wrapper handling), caching, find_search, get_search_details,
and DiscoveryService orchestration.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from veupath_chatbot.integrations.veupathdb.discovery import (
    DiscoveryService,
    SearchCatalog,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_client(
    record_types: Any = None,
    searches: dict[str, list[Any]] | None = None,
    search_details: dict[str, Any] | None = None,
) -> MagicMock:
    """Build a mock VEuPathDBClient with configurable return values."""
    client = MagicMock()
    client.get_record_types = AsyncMock(return_value=record_types or [])
    if searches:
        client.get_searches = AsyncMock(side_effect=lambda rt: searches.get(rt, []))
    else:
        client.get_searches = AsyncMock(return_value=[])
    client.get_search_details = AsyncMock(return_value=search_details or {})
    return client


# ---------------------------------------------------------------------------
# SearchCatalog.load — expanded record types (searches inlined)
# ---------------------------------------------------------------------------


class TestSearchCatalogLoadExpanded:
    """Test loading catalogs from expanded record-type responses."""

    @pytest.mark.asyncio
    async def test_load_expanded_record_types_with_inline_searches(self) -> None:
        raw = [
            {
                "urlSegment": "gene",
                "name": "Genes",
                "searches": [
                    {"urlSegment": "GenesByTaxon", "displayName": "Genes by Taxon"},
                    {"urlSegment": "GenesByOrthologs", "displayName": "Orthologs"},
                ],
            },
            {
                "urlSegment": "transcript",
                "name": "Transcripts",
                "searches": [
                    {"urlSegment": "TranscriptsByTaxon"},
                ],
            },
        ]
        client = _mock_client(record_types=raw)
        catalog = SearchCatalog("plasmodb")
        await catalog.load(client)

        assert len(catalog.get_record_types()) == 2
        gene_searches = catalog.get_searches("gene")
        assert len(gene_searches) == 2
        assert catalog.get_searches("transcript") == [
            {"urlSegment": "TranscriptsByTaxon"}
        ]

    @pytest.mark.asyncio
    async def test_load_does_not_reload_when_already_loaded(self) -> None:
        client = _mock_client(
            record_types=[{"urlSegment": "gene", "name": "Genes", "searches": []}]
        )
        catalog = SearchCatalog("plasmodb")
        await catalog.load(client)
        await catalog.load(client)  # second call should short-circuit
        # get_record_types called only once
        assert client.get_record_types.call_count == 1


# ---------------------------------------------------------------------------
# SearchCatalog.load — non-expanded (plain list)
# ---------------------------------------------------------------------------


class TestSearchCatalogLoadNonExpanded:
    """Test loading catalogs from non-expanded record-type responses."""

    @pytest.mark.asyncio
    async def test_load_string_record_types_fetches_searches(self) -> None:
        """When record types are plain strings, searches must be fetched separately."""
        client = _mock_client(
            record_types=["gene", "transcript"],
            searches={
                "gene": [{"urlSegment": "GenesByTaxon"}],
                "transcript": [{"urlSegment": "TranscriptsByTaxon"}],
            },
        )
        catalog = SearchCatalog("plasmodb")
        await catalog.load(client)

        assert len(catalog.get_record_types()) == 2
        assert catalog.get_searches("gene") == [{"urlSegment": "GenesByTaxon"}]

    @pytest.mark.asyncio
    async def test_load_dict_record_types_without_searches_fetches_them(self) -> None:
        """Dicts without an inline 'searches' key cause a per-RT fetch."""
        raw = [
            {"urlSegment": "gene", "name": "Genes"},  # no 'searches' key
        ]
        client = _mock_client(
            record_types=raw,
            searches={"gene": [{"urlSegment": "GenesByTaxon"}]},
        )
        catalog = SearchCatalog("plasmodb")
        await catalog.load(client)

        assert catalog.get_searches("gene") == [{"urlSegment": "GenesByTaxon"}]
        client.get_searches.assert_called_once_with("gene")


# ---------------------------------------------------------------------------
# SearchCatalog.load — wrapped response ({recordTypes: [...]})
# ---------------------------------------------------------------------------


class TestSearchCatalogLoadWrapped:
    """Test handling of the dict wrapper some WDK deployments use."""

    @pytest.mark.asyncio
    async def test_load_dict_wrapper_unwraps_record_types(self) -> None:
        wrapped: dict[str, Any] = {
            "recordTypes": [
                {"urlSegment": "gene", "name": "Genes", "searches": []},
            ]
        }
        client = _mock_client(record_types=wrapped)
        catalog = SearchCatalog("plasmodb")
        await catalog.load(client)

        rts = catalog.get_record_types()
        assert len(rts) == 1
        first = rts[0]
        assert isinstance(first, dict)
        assert first["urlSegment"] == "gene"

    @pytest.mark.asyncio
    async def test_load_dict_wrapper_without_record_types_key_raises(self) -> None:
        bad_wrapped: dict[str, Any] = {"somethingElse": []}
        client = _mock_client(record_types=bad_wrapped)
        catalog = SearchCatalog("plasmodb")

        with pytest.raises(TypeError, match="Unexpected record-types response shape"):
            await catalog.load(client)


# ---------------------------------------------------------------------------
# SearchCatalog — find_search / get_search_details
# ---------------------------------------------------------------------------


class TestSearchCatalogLookup:
    """Test catalog search and detail lookups."""

    @pytest.mark.asyncio
    async def test_find_search_returns_matching_search(self) -> None:
        raw = [
            {
                "urlSegment": "gene",
                "name": "Genes",
                "searches": [
                    {"urlSegment": "GenesByTaxon", "displayName": "By Taxon"},
                    {"urlSegment": "GenesByOrthologs", "displayName": "By Orthologs"},
                ],
            },
        ]
        client = _mock_client(record_types=raw)
        catalog = SearchCatalog("plasmodb")
        await catalog.load(client)

        result = catalog.find_search("gene", "GenesByOrthologs")
        assert result is not None
        assert result["displayName"] == "By Orthologs"

    @pytest.mark.asyncio
    async def test_find_search_returns_none_for_missing(self) -> None:
        raw = [
            {
                "urlSegment": "gene",
                "name": "Genes",
                "searches": [{"urlSegment": "GenesByTaxon"}],
            },
        ]
        client = _mock_client(record_types=raw)
        catalog = SearchCatalog("plasmodb")
        await catalog.load(client)

        assert catalog.find_search("gene", "Nonexistent") is None
        assert catalog.find_search("nonexistent_type", "GenesByTaxon") is None

    @pytest.mark.asyncio
    async def test_get_search_details_caches_results(self) -> None:
        details = {"urlSegment": "GenesByTaxon", "parameters": []}
        client = _mock_client(
            record_types=[{"urlSegment": "gene", "name": "Genes", "searches": []}],
            search_details=details,
        )
        catalog = SearchCatalog("plasmodb")
        await catalog.load(client)

        r1 = await catalog.get_search_details(client, "gene", "GenesByTaxon")
        r2 = await catalog.get_search_details(client, "gene", "GenesByTaxon")
        assert r1 == r2
        # Underlying client called only once due to caching
        assert client.get_search_details.call_count == 1

    @pytest.mark.asyncio
    async def test_get_search_details_expand_param_varies_cache_key(self) -> None:
        details = {"urlSegment": "GenesByTaxon"}
        client = _mock_client(
            record_types=[{"urlSegment": "gene", "name": "Genes", "searches": []}],
            search_details=details,
        )
        catalog = SearchCatalog("plasmodb")
        await catalog.load(client)

        await catalog.get_search_details(
            client, "gene", "GenesByTaxon", expand_params=True
        )
        await catalog.get_search_details(
            client, "gene", "GenesByTaxon", expand_params=False
        )
        # Two different cache keys, so two calls
        assert client.get_search_details.call_count == 2


# ---------------------------------------------------------------------------
# SearchCatalog — edge cases
# ---------------------------------------------------------------------------


class TestSearchCatalogEdgeCases:
    """Test edge cases and error resilience."""

    @pytest.mark.asyncio
    async def test_get_searches_unknown_record_type_returns_empty(self) -> None:
        catalog = SearchCatalog("plasmodb")
        raw = [
            {"urlSegment": "gene", "name": "Genes", "searches": [{"urlSegment": "s1"}]}
        ]
        client = _mock_client(record_types=raw)
        await catalog.load(client)

        assert catalog.get_searches("nonexistent") == []

    @pytest.mark.asyncio
    async def test_load_skips_non_dict_non_str_elements(self) -> None:
        """Elements that are neither str nor dict should be skipped."""
        raw = [42, None, {"urlSegment": "gene", "name": "Genes", "searches": []}]
        client = _mock_client(record_types=raw)
        catalog = SearchCatalog("plasmodb")
        await catalog.load(client)

        assert len(catalog.get_record_types()) == 1

    @pytest.mark.asyncio
    async def test_load_handles_failed_search_fetch_gracefully(self) -> None:
        """If fetching searches for one RT fails, others should still load."""
        raw = [
            {"urlSegment": "gene", "name": "Genes"},
            {"urlSegment": "transcript", "name": "Transcripts"},
        ]

        async def _get_searches(rt: str) -> list[Any]:
            if rt == "gene":
                msg = "Network error"
                raise RuntimeError(msg)
            return [{"urlSegment": "TranscriptsByTaxon"}]

        client = _mock_client(record_types=raw)
        client.get_searches = AsyncMock(side_effect=_get_searches)

        catalog = SearchCatalog("plasmodb")
        await catalog.load(client)

        # gene searches failed but transcript succeeded
        assert catalog.get_searches("gene") == []
        assert catalog.get_searches("transcript") == [
            {"urlSegment": "TranscriptsByTaxon"}
        ]

    @pytest.mark.asyncio
    async def test_find_search_skips_non_dict_search_entries(self) -> None:
        """Non-dict entries in the searches list should be skipped."""
        raw = [
            {
                "urlSegment": "gene",
                "name": "Genes",
                "searches": [
                    "not_a_dict",
                    {"urlSegment": "GenesByTaxon"},
                ],
            },
        ]
        client = _mock_client(record_types=raw)
        catalog = SearchCatalog("plasmodb")
        await catalog.load(client)

        result = catalog.find_search("gene", "GenesByTaxon")
        assert result is not None


# ---------------------------------------------------------------------------
# DiscoveryService
# ---------------------------------------------------------------------------


class TestDiscoveryService:
    """Test the DiscoveryService orchestration layer."""

    @pytest.mark.asyncio
    async def test_get_catalog_creates_and_caches(self) -> None:
        mock_client = _mock_client(
            record_types=[{"urlSegment": "gene", "name": "Genes", "searches": []}]
        )
        mock_router = MagicMock()
        mock_router.get_client.return_value = mock_client

        with patch(
            "veupath_chatbot.integrations.veupathdb.discovery.get_site_router",
            return_value=mock_router,
        ):
            service = DiscoveryService()
            c1 = await service.get_catalog("plasmodb")
            c2 = await service.get_catalog("plasmodb")
            assert c1 is c2

    @pytest.mark.asyncio
    async def test_get_record_types_delegates_to_catalog(self) -> None:
        mock_client = _mock_client(
            record_types=[
                {"urlSegment": "gene", "name": "Genes", "searches": []},
                {"urlSegment": "transcript", "name": "Transcripts", "searches": []},
            ]
        )
        mock_router = MagicMock()
        mock_router.get_client.return_value = mock_client

        with patch(
            "veupath_chatbot.integrations.veupathdb.discovery.get_site_router",
            return_value=mock_router,
        ):
            service = DiscoveryService()
            rts = await service.get_record_types("plasmodb")
            assert len(rts) == 2

    @pytest.mark.asyncio
    async def test_get_searches_delegates_to_catalog(self) -> None:
        mock_client = _mock_client(
            record_types=[
                {
                    "urlSegment": "gene",
                    "name": "Genes",
                    "searches": [{"urlSegment": "GenesByTaxon"}],
                }
            ]
        )
        mock_router = MagicMock()
        mock_router.get_client.return_value = mock_client

        with patch(
            "veupath_chatbot.integrations.veupathdb.discovery.get_site_router",
            return_value=mock_router,
        ):
            service = DiscoveryService()
            searches = await service.get_searches("plasmodb", "gene")
            assert len(searches) == 1

    @pytest.mark.asyncio
    async def test_get_search_details_delegates(self) -> None:
        details = {"urlSegment": "GenesByTaxon", "parameters": [{"name": "organism"}]}
        mock_client = _mock_client(
            record_types=[{"urlSegment": "gene", "name": "Genes", "searches": []}],
            search_details=details,
        )
        mock_router = MagicMock()
        mock_router.get_client.return_value = mock_client

        with patch(
            "veupath_chatbot.integrations.veupathdb.discovery.get_site_router",
            return_value=mock_router,
        ):
            service = DiscoveryService()
            result = await service.get_search_details(
                "plasmodb", "gene", "GenesByTaxon"
            )
            params = result["parameters"]
            assert isinstance(params, list)
            first_param = params[0]
            assert isinstance(first_param, dict)
            assert first_param["name"] == "organism"

    @pytest.mark.asyncio
    async def test_preload_all_loads_every_site(self) -> None:
        mock_client = _mock_client(
            record_types=[{"urlSegment": "gene", "name": "Genes", "searches": []}]
        )

        site_a = MagicMock()
        site_a.id = "plasmodb"
        site_b = MagicMock()
        site_b.id = "toxodb"

        mock_router = MagicMock()
        mock_router.list_sites.return_value = [site_a, site_b]
        mock_router.get_client.return_value = mock_client

        with patch(
            "veupath_chatbot.integrations.veupathdb.discovery.get_site_router",
            return_value=mock_router,
        ):
            service = DiscoveryService()
            await service.preload_all()
            assert "plasmodb" in service._catalogs
            assert "toxodb" in service._catalogs

    @pytest.mark.asyncio
    async def test_preload_all_continues_on_site_failure(self) -> None:
        """If one site fails to load, others should still succeed."""
        call_count = 0

        async def _get_record_types(*, expanded: bool = False) -> list[Any]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                msg = "Boom"
                raise RuntimeError(msg)
            return [{"urlSegment": "gene", "name": "Genes", "searches": []}]

        mock_client = MagicMock()
        mock_client.get_record_types = AsyncMock(side_effect=_get_record_types)
        mock_client.get_searches = AsyncMock(return_value=[])

        site_a = MagicMock()
        site_a.id = "failing_site"
        site_b = MagicMock()
        site_b.id = "good_site"

        mock_router = MagicMock()
        mock_router.list_sites.return_value = [site_a, site_b]
        mock_router.get_client.return_value = mock_client

        with patch(
            "veupath_chatbot.integrations.veupathdb.discovery.get_site_router",
            return_value=mock_router,
        ):
            service = DiscoveryService()
            # Should not raise even though one site fails
            await service.preload_all()
            # good_site should be loaded
            assert "good_site" in service._catalogs

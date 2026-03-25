"""VCR-backed integration tests for catalog parameter services.

Merges tests from services/catalog/parameters.py and
services/catalog/param_resolution.py into a single file. Pure domain logic
tests remain in their respective unit test files.

Record:
    WDK_AUTH_EMAIL=<email> WDK_AUTH_PASSWORD=<pw> \
    uv run pytest src/veupath_chatbot/tests/integration/test_vcr_catalog_parameters.py -v --record-mode=all

Replay:
    uv run pytest src/veupath_chatbot/tests/integration/test_vcr_catalog_parameters.py -v
"""

from typing import Any

import pytest

from veupath_chatbot.domain.search import SearchContext
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKSearchResponse
from veupath_chatbot.services.catalog import param_resolution
from veupath_chatbot.services.catalog.param_resolution import (
    expand_search_details_with_params,
    get_search_parameters_tool,
)
from veupath_chatbot.services.catalog.parameters import get_search_parameters


def _get_param_by_name(result: dict[str, Any], name: str) -> dict[str, Any]:
    """Extract a parameter dict from get_search_parameters result by name."""
    params = result["parameters"]
    assert isinstance(params, list)
    for p in params:
        assert isinstance(p, dict)
        if p.get("name") == name:
            return p
    available = [p.get("name") for p in params if isinstance(p, dict)]
    msg = f"Parameter '{name}' not found in {available}"
    raise AssertionError(msg)


# ---------------------------------------------------------------------------
# get_search_parameters (catalog/parameters.py) — real WDK
# ---------------------------------------------------------------------------


class TestGetSearchParametersReal:
    """Test get_search_parameters against real WDK API responses."""

    @pytest.mark.vcr
    async def test_genes_by_taxon_returns_parameters(self, wdk_site_id: str) -> None:
        result = await get_search_parameters(
            SearchContext(wdk_site_id, "transcript", "GenesByTaxon")
        )

        assert result["searchName"] == "GenesByTaxon"
        assert result["displayName"]
        assert result["resolvedRecordType"] == "transcript"

        params = result["parameters"]
        assert isinstance(params, list)
        assert len(params) > 0
        for p in params:
            assert isinstance(p, dict)
            assert "name" in p
            assert "type" in p

    @pytest.mark.vcr
    async def test_parameter_has_required_field(self, wdk_site_id: str) -> None:
        result = await get_search_parameters(
            SearchContext(wdk_site_id, "transcript", "GenesByTaxon")
        )
        for p in result["parameters"]:
            assert isinstance(p, dict)
            assert "required" in p
            assert isinstance(p["required"], bool)

    @pytest.mark.vcr
    async def test_parameter_has_visibility(self, wdk_site_id: str) -> None:
        result = await get_search_parameters(
            SearchContext(wdk_site_id, "transcript", "GenesByTaxon")
        )
        for p in result["parameters"]:
            assert isinstance(p, dict)
            assert "isVisible" in p
            assert isinstance(p["isVisible"], bool)

    @pytest.mark.vcr
    async def test_organism_param_has_vocabulary(self, wdk_site_id: str) -> None:
        result = await get_search_parameters(
            SearchContext(wdk_site_id, "transcript", "GenesByTaxon")
        )
        organism = _get_param_by_name(result, "organism")
        # Organism is a tree vocab → gets allowedValues_tree, not allowedValues
        tree = organism.get("allowedValues_tree")
        assert isinstance(tree, str)
        assert len(tree) > 0

    @pytest.mark.vcr
    async def test_gene_by_locus_tag_parameters(self, wdk_site_id: str) -> None:
        result = await get_search_parameters(
            SearchContext(wdk_site_id, "transcript", "GeneByLocusTag")
        )
        assert result["searchName"] == "GeneByLocusTag"
        assert result["resolvedRecordType"] == "transcript"
        assert len(result["parameters"]) > 0

    @pytest.mark.vcr
    async def test_display_name_from_details(self, wdk_site_id: str) -> None:
        result = await get_search_parameters(
            SearchContext(wdk_site_id, "transcript", "GenesByTaxon")
        )
        assert result["displayName"]
        assert result["description"] is not None

    @pytest.mark.vcr
    async def test_allowed_values_capped_at_50(self, wdk_site_id: str) -> None:
        result = await get_search_parameters(
            SearchContext(wdk_site_id, "transcript", "GenesByTaxon")
        )
        for p in result["parameters"]:
            assert isinstance(p, dict)
            allowed = p.get("allowedValues")
            if isinstance(allowed, list):
                assert len(allowed) <= 50, (
                    f"Parameter {p['name']} should have <= 50 allowed values"
                )


# ---------------------------------------------------------------------------
# get_search_parameters (catalog/param_resolution.py) — real WDK
# ---------------------------------------------------------------------------


class TestGetSearchParametersResolvedReal:
    """Test param_resolution.get_search_parameters against real WDK."""

    @pytest.mark.vcr
    async def test_basic_search_parameters(self, wdk_site_id: str) -> None:
        result = await param_resolution.get_search_parameters(
            SearchContext(wdk_site_id, "transcript", "GenesByTaxon")
        )
        assert result["searchName"] == "GenesByTaxon"
        assert result["displayName"]
        assert result["resolvedRecordType"] == "transcript"
        assert len(result["parameters"]) > 0

    @pytest.mark.vcr
    async def test_organism_param_has_vocabulary_info(self, wdk_site_id: str) -> None:
        result = await param_resolution.get_search_parameters(
            SearchContext(wdk_site_id, "transcript", "GenesByTaxon")
        )
        organism = _get_param_by_name(result, "organism")
        # Organism is a tree vocab → gets allowedValues_tree
        tree = organism.get("allowedValues_tree")
        assert isinstance(tree, str)
        assert len(tree) > 0

    @pytest.mark.vcr
    async def test_case_insensitive_record_type_resolution(self, wdk_site_id: str) -> None:
        result = await param_resolution.get_search_parameters(
            SearchContext(wdk_site_id, "TRANSCRIPT", "GenesByTaxon")
        )
        assert result["resolvedRecordType"] == "transcript"


# ---------------------------------------------------------------------------
# get_search_parameters_tool — real WDK
# ---------------------------------------------------------------------------


class TestGetSearchParametersToolReal:
    """Test the tool-wrapper against real WDK."""

    @pytest.mark.vcr
    async def test_returns_result_on_success(self, wdk_site_id: str) -> None:
        result = await get_search_parameters_tool(
            SearchContext(wdk_site_id, "transcript", "GenesByTaxon")
        )
        assert result["searchName"] == "GenesByTaxon"
        assert "ok" not in result

    @pytest.mark.vcr
    async def test_returns_tool_error_on_nonexistent_search(self, wdk_site_id: str) -> None:
        result = await get_search_parameters_tool(
            SearchContext(wdk_site_id, "transcript", "NonexistentSearch99999")
        )
        assert result["ok"] is False
        assert "code" in result


# ---------------------------------------------------------------------------
# expand_search_details_with_params — real WDK
# ---------------------------------------------------------------------------


class TestExpandSearchDetailsReal:
    """Test expand_search_details_with_params against real WDK."""

    @pytest.mark.vcr
    async def test_basic_expansion(self, wdk_site_id: str) -> None:
        result = await expand_search_details_with_params(
            SearchContext(wdk_site_id, "transcript", "GenesByTaxon"),
            {},
        )
        assert isinstance(result, WDKSearchResponse)
        assert result.search_data.url_segment == "GenesByTaxon"

    @pytest.mark.vcr
    async def test_handles_none_context(self, wdk_site_id: str) -> None:
        result = await expand_search_details_with_params(
            SearchContext(wdk_site_id, "transcript", "GenesByTaxon"),
            None,
        )
        assert isinstance(result, WDKSearchResponse)

"""Live integration tests for phyletic profile tools.

Tests lookup_phyletic_codes and get_search_parameters phyletic trimming against
the REAL VEuPathDB WDK API at plasmodb.org. NO MOCKS.

Run with:
    pytest src/veupath_chatbot/tests/integration/test_phyletic_integration.py -v -s

Skip with:
    pytest -m "not live_wdk"
"""

from collections.abc import AsyncGenerator
from typing import Any

import pytest

from veupath_chatbot.domain.search import SearchContext
from veupath_chatbot.integrations.veupathdb.site_router import get_site_router
from veupath_chatbot.services.catalog.param_resolution import (
    get_search_parameters,
    lookup_phyletic_codes,
)

pytestmark = pytest.mark.live_wdk


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def _close_wdk_clients() -> AsyncGenerator[None]:
    """Close shared WDK httpx clients after each test."""
    yield
    try:
        router = get_site_router()
        await router.close_all()
    except RuntimeError, OSError:
        pass  # Client already closed or event loop torn down


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _param_names(result: dict[str, Any]) -> list[str]:
    """Extract parameter names from get_search_parameters result."""
    return [
        p["name"] for p in result["parameters"] if isinstance(p, dict) and "name" in p
    ]


def _find_param(result: dict[str, Any], name: str) -> dict[str, Any]:
    """Find a parameter by name in get_search_parameters result."""
    for p in result["parameters"]:
        if isinstance(p, dict) and p.get("name") == name:
            return p
    msg = f"Parameter '{name}' not found in result"
    raise AssertionError(msg)


# ===========================================================================
# 1. lookup_phyletic_codes — species/clade lookup
# ===========================================================================


class TestLookupPhyleticCodes:
    """Test lookup_phyletic_codes against the live PlasmoDB API."""

    @pytest.mark.asyncio
    async def test_finds_plasmodium_falciparum(self) -> None:
        result = await lookup_phyletic_codes("plasmodb", "transcript", "falciparum")

        assert result["total"] > 0, "Should find at least one match for 'falciparum'"
        codes = [m["code"] for m in result["matches"]]
        labels = [m["label"] for m in result["matches"]]
        assert "pfal" in codes, f"Expected 'pfal' in codes, got {codes}"
        assert any("falciparum" in lbl.lower() for lbl in labels)
        assert "%CODE:Y%" in result["hint"]

    @pytest.mark.asyncio
    async def test_finds_human(self) -> None:
        result = await lookup_phyletic_codes("plasmodb", "transcript", "sapiens")

        assert result["total"] > 0, "Should find at least one match for 'sapiens'"
        codes = [m["code"] for m in result["matches"]]
        assert "hsap" in codes, f"Expected 'hsap' in codes, got {codes}"

    @pytest.mark.asyncio
    async def test_finds_apicomplexa_clade(self) -> None:
        result = await lookup_phyletic_codes("plasmodb", "transcript", "Apicomplexa")

        assert result["total"] > 0, "Should find Apicomplexa clade"
        codes = [m["code"] for m in result["matches"]]
        assert "APIC" in codes, f"Expected 'APIC' (clade code) in codes, got {codes}"

    @pytest.mark.asyncio
    async def test_no_results_for_nonexistent(self) -> None:
        result = await lookup_phyletic_codes(
            "plasmodb", "transcript", "zzz_nonexistent_species_zzz"
        )

        assert result["total"] == 0
        assert result["matches"] == []

    @pytest.mark.asyncio
    async def test_caps_at_20_matches(self) -> None:
        """A broad query like 'a' should return at most 20 matches."""
        result = await lookup_phyletic_codes("plasmodb", "transcript", "a")

        assert len(result["matches"]) <= 20


# ===========================================================================
# 2. get_search_parameters — phyletic structural param trimming
# ===========================================================================


class TestGetSearchParametersPhyleticTrimming:
    """Test that get_search_parameters trims phyletic structural params."""

    @pytest.mark.asyncio
    async def test_structural_params_excluded(self) -> None:
        result = await get_search_parameters(
            SearchContext("plasmodb", "transcript", "GenesByOrthologPattern")
        )
        names = _param_names(result)

        assert "phyletic_indent_map" not in names, (
            "phyletic_indent_map should be trimmed from AI output"
        )
        assert "phyletic_term_map" not in names, (
            "phyletic_term_map should be trimmed from AI output"
        )

    @pytest.mark.asyncio
    async def test_essential_params_present(self) -> None:
        result = await get_search_parameters(
            SearchContext("plasmodb", "transcript", "GenesByOrthologPattern")
        )
        names = _param_names(result)

        assert "profile_pattern" in names, "profile_pattern must be present"
        assert "included_species" in names, "included_species must be present"
        assert "excluded_species" in names, "excluded_species must be present"
        assert "organism" in names, "organism must be present"

    @pytest.mark.asyncio
    async def test_profile_pattern_help_enriched(self) -> None:
        result = await get_search_parameters(
            SearchContext("plasmodb", "transcript", "GenesByOrthologPattern")
        )
        pp = _find_param(result, "profile_pattern")

        assert "%CODE:STATE" in pp["help"], (
            f"profile_pattern help should contain encoding docs, got: {pp['help']}"
        )
        assert "lookup_phyletic_codes" in pp["help"], (
            f"profile_pattern help should reference lookup tool, got: {pp['help']}"
        )


# ===========================================================================
# 3. get_search_parameters — non-phyletic search unaffected
# ===========================================================================


class TestGetSearchParametersNormalSearch:
    """Test that non-phyletic searches are unaffected by trimming logic."""

    @pytest.mark.asyncio
    async def test_genes_by_taxon_unaffected(self) -> None:
        result = await get_search_parameters(
            SearchContext("plasmodb", "transcript", "GenesByTaxon")
        )
        names = _param_names(result)

        # GenesByTaxon has organism param — it should be present
        assert "organism" in names, (
            f"GenesByTaxon should have 'organism' param, got: {names}"
        )
        # No phyletic params should exist in GenesByTaxon in the first place,
        # but verify no accidental removal of legitimate params
        assert len(names) > 0, "GenesByTaxon should have at least one parameter"

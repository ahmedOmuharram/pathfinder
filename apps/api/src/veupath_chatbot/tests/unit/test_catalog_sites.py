"""Unit tests for services/catalog/sites.py.

Covers list_sites() and get_record_types() with mocked discovery/factory.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from veupath_chatbot.services.catalog.sites import get_record_types, list_sites

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _site_info(
    site_id: str = "plasmodb",
    name: str = "PlasmoDB",
    display_name: str = "PlasmoDB",
    base_url: str = "https://plasmodb.org/plasmo/service",
    project_id: str = "PlasmoDB",
    is_portal: bool = False,
) -> MagicMock:
    si = MagicMock()
    si.id = site_id
    si.name = name
    si.display_name = display_name
    si.base_url = base_url
    si.project_id = project_id
    si.is_portal = is_portal
    si.to_dict.return_value = {
        "id": site_id,
        "name": name,
        "displayName": display_name,
        "baseUrl": base_url,
        "projectId": project_id,
        "isPortal": is_portal,
    }
    return si


def _mock_discovery(record_types: list[Any] | None = None) -> MagicMock:
    discovery = MagicMock()
    discovery.get_record_types = AsyncMock(return_value=record_types or [])
    return discovery


def _as_dict(val: object) -> dict[str, Any]:
    """Narrow a JSONValue to dict for test assertions."""
    assert isinstance(val, dict)
    return val


# ---------------------------------------------------------------------------
# list_sites
# ---------------------------------------------------------------------------


class TestListSites:
    """Test the list_sites() function."""

    async def test_returns_all_sites_as_dicts(self) -> None:
        sites = [
            _site_info(site_id="plasmodb"),
            _site_info(site_id="toxodb", name="ToxoDB", display_name="ToxoDB"),
        ]
        with patch(
            "veupath_chatbot.services.catalog.sites.list_wdk_sites",
            return_value=sites,
        ):
            result = await list_sites()

        assert len(result) == 2
        assert _as_dict(result[0])["id"] == "plasmodb"
        assert _as_dict(result[1])["id"] == "toxodb"

    async def test_returns_empty_when_no_sites(self) -> None:
        with patch(
            "veupath_chatbot.services.catalog.sites.list_wdk_sites",
            return_value=[],
        ):
            result = await list_sites()

        assert result == []

    async def test_single_site_structure(self) -> None:
        sites = [_site_info()]
        with patch(
            "veupath_chatbot.services.catalog.sites.list_wdk_sites",
            return_value=sites,
        ):
            result = await list_sites()

        assert len(result) == 1
        d = _as_dict(result[0])
        assert d["id"] == "plasmodb"
        assert d["name"] == "PlasmoDB"
        assert d["displayName"] == "PlasmoDB"
        assert d["baseUrl"] == "https://plasmodb.org/plasmo/service"
        assert d["projectId"] == "PlasmoDB"
        assert d["isPortal"] is False


# ---------------------------------------------------------------------------
# get_record_types
# ---------------------------------------------------------------------------


class TestGetRecordTypes:
    """Test the get_record_types() function."""

    async def test_extracts_url_segment_and_display_name(self) -> None:
        discovery = _mock_discovery(
            record_types=[
                {
                    "urlSegment": "gene",
                    "name": "GeneRecordClasses.GeneRecordClass",
                    "displayName": "Genes",
                    "description": "Gene records",
                },
            ]
        )
        with patch(
            "veupath_chatbot.services.catalog.sites.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_record_types("plasmodb")

        assert len(result) == 1
        rt = _as_dict(result[0])
        assert rt["name"] == "gene"
        assert rt["displayName"] == "Genes"
        assert rt["description"] == "Gene records"

    async def test_prefers_url_segment_over_name(self) -> None:
        discovery = _mock_discovery(
            record_types=[
                {
                    "urlSegment": "gene",
                    "name": "GeneRecordClasses.GeneRecordClass",
                },
            ]
        )
        with patch(
            "veupath_chatbot.services.catalog.sites.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_record_types("plasmodb")

        assert _as_dict(result[0])["name"] == "gene"

    async def test_falls_back_to_name_when_no_url_segment(self) -> None:
        discovery = _mock_discovery(
            record_types=[
                {
                    "name": "GeneRecordClasses.GeneRecordClass",
                    "displayName": "Genes",
                },
            ]
        )
        with patch(
            "veupath_chatbot.services.catalog.sites.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_record_types("plasmodb")

        assert _as_dict(result[0])["name"] == "GeneRecordClasses.GeneRecordClass"

    async def test_handles_missing_optional_fields(self) -> None:
        discovery = _mock_discovery(
            record_types=[
                {"urlSegment": "gene"},
            ]
        )
        with patch(
            "veupath_chatbot.services.catalog.sites.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_record_types("plasmodb")

        rt = _as_dict(result[0])
        assert rt["name"] == "gene"
        assert rt["displayName"] is None
        assert rt["description"] == ""

    async def test_skips_non_dict_entries(self) -> None:
        discovery = _mock_discovery(
            record_types=[
                "not_a_dict",
                42,
                None,
                {"urlSegment": "gene", "displayName": "Genes"},
            ]
        )
        with patch(
            "veupath_chatbot.services.catalog.sites.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_record_types("plasmodb")

        assert len(result) == 1
        assert _as_dict(result[0])["name"] == "gene"

    async def test_empty_record_types(self) -> None:
        discovery = _mock_discovery(record_types=[])
        with patch(
            "veupath_chatbot.services.catalog.sites.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_record_types("plasmodb")

        assert result == []

    async def test_multiple_record_types(self) -> None:
        discovery = _mock_discovery(
            record_types=[
                {"urlSegment": "gene", "displayName": "Genes"},
                {"urlSegment": "transcript", "displayName": "Transcripts"},
                {"urlSegment": "organism", "displayName": "Organisms"},
            ]
        )
        with patch(
            "veupath_chatbot.services.catalog.sites.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_record_types("plasmodb")

        assert len(result) == 3
        names = [_as_dict(r)["name"] for r in result]
        assert names == ["gene", "transcript", "organism"]

    async def test_non_string_url_segment_ignored(self) -> None:
        """When urlSegment is not a string, it should fall back to name."""
        discovery = _mock_discovery(
            record_types=[
                {"urlSegment": 123, "name": "fallback_name"},
            ]
        )
        with patch(
            "veupath_chatbot.services.catalog.sites.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_record_types("plasmodb")

        assert _as_dict(result[0])["name"] == "fallback_name"

    async def test_both_url_segment_and_name_missing(self) -> None:
        """When neither urlSegment nor name exists, name should be empty."""
        discovery = _mock_discovery(
            record_types=[
                {"displayName": "Something"},
            ]
        )
        with patch(
            "veupath_chatbot.services.catalog.sites.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_record_types("plasmodb")

        assert _as_dict(result[0])["name"] == ""

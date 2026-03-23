"""Unit tests for services/catalog/sites.py.

Covers list_sites() and get_record_types() with mocked discovery/factory.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from veupath_chatbot.integrations.veupathdb.site_router import SiteInfo
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKRecordType
from veupath_chatbot.services.catalog.models import RecordTypeInfo
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
) -> SiteInfo:
    return SiteInfo(
        id=site_id,
        name=name,
        display_name=display_name,
        base_url=base_url,
        project_id=project_id,
        is_portal=is_portal,
    )


def _mock_discovery(record_types: list[WDKRecordType] | None = None) -> MagicMock:
    discovery = MagicMock()
    discovery.get_record_types = AsyncMock(return_value=record_types or [])
    return discovery


def _wdk_rt(
    url_segment: str,
    display_name: str = "",
    description: str = "",
    full_name: str = "",
) -> WDKRecordType:
    """Build a WDKRecordType for testing."""
    return WDKRecordType(
        url_segment=url_segment,
        display_name=display_name,
        description=description,
        full_name=full_name,
    )


# ---------------------------------------------------------------------------
# list_sites
# ---------------------------------------------------------------------------


class TestListSites:
    """Test the list_sites() function."""

    async def test_returns_all_sites(self) -> None:
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
        assert result[0].id == "plasmodb"
        assert result[1].id == "toxodb"

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
        s = result[0]
        assert s.id == "plasmodb"
        assert s.name == "PlasmoDB"
        assert s.display_name == "PlasmoDB"
        assert s.base_url == "https://plasmodb.org/plasmo/service"
        assert s.project_id == "PlasmoDB"
        assert s.is_portal is False

    async def test_returns_site_info_objects(self) -> None:
        """list_sites should return SiteInfo typed models, not dicts."""
        sites = [_site_info()]
        with patch(
            "veupath_chatbot.services.catalog.sites.list_wdk_sites",
            return_value=sites,
        ):
            result = await list_sites()

        assert isinstance(result[0], SiteInfo)


# ---------------------------------------------------------------------------
# get_record_types
# ---------------------------------------------------------------------------


class TestGetRecordTypes:
    """Test the get_record_types() function."""

    async def test_extracts_url_segment_and_display_name(self) -> None:
        discovery = _mock_discovery(
            record_types=[
                _wdk_rt(
                    url_segment="gene",
                    display_name="Genes",
                    description="Gene records",
                    full_name="GeneRecordClasses.GeneRecordClass",
                ),
            ]
        )
        with patch(
            "veupath_chatbot.services.catalog.sites.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_record_types("plasmodb")

        assert len(result) == 1
        rt = result[0]
        assert rt.name == "gene"
        assert rt.display_name == "Genes"
        assert rt.description == "Gene records"

    async def test_handles_missing_optional_fields(self) -> None:
        discovery = _mock_discovery(record_types=[_wdk_rt(url_segment="gene")])
        with patch(
            "veupath_chatbot.services.catalog.sites.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_record_types("plasmodb")

        rt = result[0]
        assert rt.name == "gene"
        assert rt.display_name == ""
        assert rt.description == ""

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
                _wdk_rt(url_segment="gene", display_name="Genes"),
                _wdk_rt(url_segment="transcript", display_name="Transcripts"),
                _wdk_rt(url_segment="organism", display_name="Organisms"),
            ]
        )
        with patch(
            "veupath_chatbot.services.catalog.sites.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_record_types("plasmodb")

        assert len(result) == 3
        names = [r.name for r in result]
        assert names == ["gene", "transcript", "organism"]

    async def test_returns_record_type_info_objects(self) -> None:
        """get_record_types should return RecordTypeInfo typed models."""
        discovery = _mock_discovery(
            record_types=[_wdk_rt(url_segment="gene", display_name="Genes")]
        )
        with patch(
            "veupath_chatbot.services.catalog.sites.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_record_types("plasmodb")

        assert isinstance(result[0], RecordTypeInfo)

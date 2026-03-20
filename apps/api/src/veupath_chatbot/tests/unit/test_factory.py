"""Unit tests for veupath_chatbot.integrations.veupathdb.factory.

Tests the integration entrypoints: get_wdk_client, get_site, list_sites,
get_strategy_api, get_results_api, close_all_clients.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from veupath_chatbot.integrations.veupathdb.factory import (
    close_all_clients,
    get_results_api,
    get_site,
    get_strategy_api,
    get_wdk_client,
    list_sites,
)
from veupath_chatbot.integrations.veupathdb.site_router import SiteInfo
from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.integrations.veupathdb.temporary_results import TemporaryResultsAPI


def _make_site(site_id: str = "plasmodb") -> SiteInfo:
    return SiteInfo(
        site_id=site_id,
        name="PlasmoDB",
        display_name="PlasmoDB",
        base_url="https://plasmodb.org/plasmo/service",
        project_id="PlasmoDB",
        is_portal=False,
    )


def _mock_router(sites: list[SiteInfo] | None = None) -> MagicMock:
    router = MagicMock()
    default_site = _make_site()
    default_client = MagicMock()
    default_client.base_url = "https://plasmodb.org/plasmo/service"

    router.get_site.return_value = default_site
    router.get_client.return_value = default_client
    router.list_sites.return_value = sites or [default_site]
    router.close_all = AsyncMock()
    return router


class TestGetWdkClient:
    """get_wdk_client delegates to site router."""

    def test_returns_client_for_site(self) -> None:
        mock_router = _mock_router()
        with patch(
            "veupath_chatbot.integrations.veupathdb.factory.get_site_router",
            return_value=mock_router,
        ):
            client = get_wdk_client("plasmodb")
        mock_router.get_client.assert_called_once_with("plasmodb")
        assert client is mock_router.get_client.return_value


class TestGetSite:
    """get_site delegates to site router."""

    def test_returns_site_info(self) -> None:
        mock_router = _mock_router()
        with patch(
            "veupath_chatbot.integrations.veupathdb.factory.get_site_router",
            return_value=mock_router,
        ):
            site = get_site("plasmodb")
        mock_router.get_site.assert_called_once_with("plasmodb")
        assert site.id == "plasmodb"


class TestListSites:
    """list_sites returns all sites from router."""

    def test_returns_all_sites(self) -> None:
        sites = [_make_site("plasmodb"), _make_site("toxodb")]
        mock_router = _mock_router(sites)
        with patch(
            "veupath_chatbot.integrations.veupathdb.factory.get_site_router",
            return_value=mock_router,
        ):
            result = list_sites()
        assert len(result) == 2


class TestGetStrategyApi:
    """get_strategy_api returns a StrategyAPI wrapper."""

    def test_returns_strategy_api(self) -> None:
        mock_router = _mock_router()
        with patch(
            "veupath_chatbot.integrations.veupathdb.factory.get_site_router",
            return_value=mock_router,
        ):
            api = get_strategy_api("plasmodb")
        assert isinstance(api, StrategyAPI)
        assert api.client is mock_router.get_client.return_value


class TestGetResultsApi:
    """get_results_api returns a TemporaryResultsAPI wrapper."""

    def test_returns_temporary_results_api(self) -> None:
        mock_router = _mock_router()
        with patch(
            "veupath_chatbot.integrations.veupathdb.factory.get_site_router",
            return_value=mock_router,
        ):
            api = get_results_api("plasmodb")
        assert isinstance(api, TemporaryResultsAPI)
        assert api.client is mock_router.get_client.return_value


class TestCloseAllClients:
    """close_all_clients delegates to router.close_all."""

    async def test_calls_router_close_all(self) -> None:
        mock_router = _mock_router()
        with patch(
            "veupath_chatbot.integrations.veupathdb.factory.get_site_router",
            return_value=mock_router,
        ):
            await close_all_clients()
        mock_router.close_all.assert_awaited_once()

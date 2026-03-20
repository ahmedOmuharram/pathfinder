"""Unit tests for the site router module.

Covers SiteInfo properties, SiteRouter site lookup / client creation /
caching / error handling, and routing preferences.
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from veupath_chatbot.integrations.veupathdb.site_router import (
    SiteConfig,
    SiteInfo,
    SiteRouter,
    SitesConfig,
)
from veupath_chatbot.platform.errors import ErrorCode, NotFoundError

# ---------------------------------------------------------------------------
# SiteInfo
# ---------------------------------------------------------------------------


class TestSiteInfo:
    """Tests for the SiteInfo value object."""

    def _make_site(self, **overrides: Any) -> SiteInfo:
        defaults: dict[str, Any] = {
            "site_id": "plasmodb",
            "name": "PlasmoDB",
            "display_name": "PlasmoDB (Plasmodium)",
            "base_url": "https://plasmodb.org/plasmo/service",
            "project_id": "PlasmoDB",
            "is_portal": False,
        }
        defaults.update(overrides)
        return SiteInfo(**defaults)

    def test_service_url_returns_base_url(self) -> None:
        site = self._make_site()
        assert site.service_url == "https://plasmodb.org/plasmo/service"

    def test_base_url_trailing_slash_stripped(self) -> None:
        site = self._make_site(base_url="https://example.com/service/")
        assert site.base_url == "https://example.com/service"

    def test_web_base_url_strips_service_suffix(self) -> None:
        site = self._make_site(base_url="https://plasmodb.org/plasmo/service")
        assert site.web_base_url == "https://plasmodb.org/plasmo"

    def test_web_base_url_no_service_suffix(self) -> None:
        site = self._make_site(base_url="https://plasmodb.org/plasmo")
        assert site.web_base_url == "https://plasmodb.org/plasmo"

    def test_strategy_url_without_root_step(self) -> None:
        site = self._make_site()
        url = site.strategy_url(42)
        assert url == "https://plasmodb.org/plasmo/app/workspace/strategies/42"

    def test_strategy_url_with_root_step(self) -> None:
        site = self._make_site()
        url = site.strategy_url(42, root_step_id=99)
        assert url == "https://plasmodb.org/plasmo/app/workspace/strategies/42/99"

    def test_to_dict_contains_all_fields(self) -> None:
        site = self._make_site()
        d = site.to_dict()
        assert d["id"] == "plasmodb"
        assert d["name"] == "PlasmoDB"
        assert d["displayName"] == "PlasmoDB (Plasmodium)"
        assert d["baseUrl"] == "https://plasmodb.org/plasmo/service"
        assert d["projectId"] == "PlasmoDB"
        assert d["isPortal"] is False

    def test_portal_site_is_portal_true(self) -> None:
        site = self._make_site(site_id="veupathdb", is_portal=True)
        assert site.is_portal is True
        assert site.to_dict()["isPortal"] is True

    def test_from_config_factory(self) -> None:
        cfg = SiteConfig(
            name="PlasmoDB",
            display_name="PlasmoDB (Plasmodium)",
            base_url="https://plasmodb.org/plasmo/service",
            project_id="PlasmoDB",
            is_portal=False,
        )
        site = SiteInfo.from_config("plasmodb", cfg)
        assert site.id == "plasmodb"
        assert site.name == "PlasmoDB"
        assert site.display_name == "PlasmoDB (Plasmodium)"
        assert site.is_portal is False


# ---------------------------------------------------------------------------
# SiteRouter
# ---------------------------------------------------------------------------


_MINIMAL_CONFIG = SitesConfig.model_validate(
    {
        "sites": {
            "plasmodb": {
                "name": "PlasmoDB",
                "display_name": "PlasmoDB (Plasmodium)",
                "base_url": "https://plasmodb.org/plasmo/service",
                "project_id": "PlasmoDB",
                "is_portal": False,
            },
            "veupathdb": {
                "name": "VEuPathDB",
                "display_name": "VEuPathDB Portal",
                "base_url": "https://veupathdb.org/veupathdb/service",
                "project_id": "EuPathDB",
                "is_portal": True,
            },
        },
        "default_site": "plasmodb",
        "routing": {
            "portal_timeout": 120,
            "component_timeout": 30,
        },
    }
)


def _make_router(config: SitesConfig | dict[str, Any] | None = None) -> SiteRouter:
    """Build a SiteRouter backed by the given config.

    Accepts either a SitesConfig model or a raw dict (auto-validated).
    """
    if config is None:
        resolved = _MINIMAL_CONFIG
    elif isinstance(config, dict):
        resolved = SitesConfig.model_validate(config)
    else:
        resolved = config
    with patch(
        "veupath_chatbot.integrations.veupathdb.site_router.load_sites_config",
        return_value=resolved,
    ):
        return SiteRouter()


class TestSiteRouterSiteLookup:
    """Test site lookup, listing, and error handling."""

    def test_get_site_returns_site_info(self) -> None:
        router = _make_router()
        site = router.get_site("plasmodb")
        assert site.id == "plasmodb"
        assert site.name == "PlasmoDB"
        assert site.is_portal is False

    def test_get_site_unknown_raises_not_found(self) -> None:
        router = _make_router()
        with pytest.raises(NotFoundError) as exc_info:
            router.get_site("nonexistent")
        assert exc_info.value.code == ErrorCode.SITE_NOT_FOUND

    def test_list_sites_returns_all(self) -> None:
        router = _make_router()
        sites = router.list_sites()
        ids = {s.id for s in sites}
        assert ids == {"plasmodb", "veupathdb"}

    def test_get_default_site(self) -> None:
        router = _make_router()
        with patch(
            "veupath_chatbot.integrations.veupathdb.site_router.get_settings"
        ) as mock_settings:
            mock_settings.return_value = MagicMock(veupathdb_default_site="plasmodb")
            site = router.get_default_site()
            assert site.id == "plasmodb"

    def test_get_default_site_from_config(self) -> None:
        config = SitesConfig(
            sites=_MINIMAL_CONFIG.sites,
            default_site="veupathdb",
            routing=_MINIMAL_CONFIG.routing,
        )
        router = _make_router(config)
        with patch(
            "veupath_chatbot.integrations.veupathdb.site_router.get_settings"
        ) as mock_settings:
            mock_settings.return_value = MagicMock(veupathdb_default_site="plasmodb")
            site = router.get_default_site()
            assert site.id == "veupathdb"


class TestSiteRouterClientCreation:
    """Test HTTP client creation and caching."""

    def test_get_client_creates_client_for_site(self) -> None:
        router = _make_router()
        with patch(
            "veupath_chatbot.integrations.veupathdb.site_router.get_settings"
        ) as mock_settings:
            mock_settings.return_value = MagicMock(veupathdb_auth_token=None)
            client = router.get_client("plasmodb")
        assert client.base_url == "https://plasmodb.org/plasmo/service"
        assert client.timeout == 30.0  # component timeout

    def test_get_client_portal_uses_portal_timeout(self) -> None:
        router = _make_router()
        with patch(
            "veupath_chatbot.integrations.veupathdb.site_router.get_settings"
        ) as mock_settings:
            mock_settings.return_value = MagicMock(veupathdb_auth_token=None)
            client = router.get_client("veupathdb")
        assert client.timeout == 120.0

    def test_get_client_caches_client(self) -> None:
        router = _make_router()
        with patch(
            "veupath_chatbot.integrations.veupathdb.site_router.get_settings"
        ) as mock_settings:
            mock_settings.return_value = MagicMock(veupathdb_auth_token=None)
            c1 = router.get_client("plasmodb")
            c2 = router.get_client("plasmodb")
        assert c1 is c2

    def test_get_portal_client_returns_veupathdb(self) -> None:
        router = _make_router()
        with patch(
            "veupath_chatbot.integrations.veupathdb.site_router.get_settings"
        ) as mock_settings:
            mock_settings.return_value = MagicMock(veupathdb_auth_token=None)
            client = router.get_portal_client()
        assert client.base_url == "https://veupathdb.org/veupathdb/service"


class TestSiteRouterCloseAll:
    """Test async close_all cleanup."""

    @pytest.mark.asyncio
    async def test_close_all_clears_clients(self) -> None:
        router = _make_router()
        with patch(
            "veupath_chatbot.integrations.veupathdb.site_router.get_settings"
        ) as mock_settings:
            mock_settings.return_value = MagicMock(veupathdb_auth_token=None)
            router.get_client("plasmodb")
        assert len(router._clients) == 1

        # Patch each cached client's close() to be a no-op coroutine
        async def _noop() -> None:
            pass

        for c in router._clients.values():
            object.__setattr__(c, "close", _noop)

        await router.close_all()
        assert len(router._clients) == 0


class TestSiteRouterEdgeCases:
    """Test malformed config handling."""

    def test_empty_sites_config_is_handled(self) -> None:
        config = SitesConfig(sites={}, default_site="plasmodb")
        router = _make_router(config)
        assert router.list_sites() == []

    def test_missing_routing_config_uses_defaults(self) -> None:
        config = SitesConfig(
            sites=_MINIMAL_CONFIG.sites,
            default_site="plasmodb",
            # routing defaults to RoutingConfig()
        )
        router = _make_router(config)
        with patch(
            "veupath_chatbot.integrations.veupathdb.site_router.get_settings"
        ) as mock_settings:
            mock_settings.return_value = MagicMock(veupathdb_auth_token=None)
            client = router.get_client("plasmodb")
        # Default component_timeout = 30
        assert client.timeout == 30.0


class TestSiteConfigValidation:
    """Test Pydantic config model validation."""

    def test_site_config_defaults(self) -> None:
        cfg = SiteConfig()
        assert cfg.name == ""
        assert cfg.is_portal is False

    def test_sites_config_from_yaml_dict(self) -> None:
        raw = {
            "sites": {
                "test": {
                    "name": "TestDB",
                    "display_name": "Test Database",
                    "base_url": "https://test.org/service",
                    "project_id": "Test",
                    "is_portal": False,
                }
            },
            "default_site": "test",
            "routing": {"portal_timeout": 60, "component_timeout": 15},
        }
        config = SitesConfig.model_validate(raw)
        assert "test" in config.sites
        assert config.sites["test"].name == "TestDB"
        assert config.routing.portal_timeout == 60.0
        assert config.routing.component_timeout == 15.0

    def test_sites_config_missing_fields_use_defaults(self) -> None:
        config = SitesConfig.model_validate({})
        assert config.sites == {}
        assert config.default_site == "veupathdb"
        assert config.routing.portal_timeout == 120.0

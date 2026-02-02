"""Site routing: choose portal vs component sites intelligently."""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.errors import NotFoundError, ErrorCode
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.integrations.veupathdb.client import VEuPathDBClient

logger = get_logger(__name__)


@lru_cache
def load_sites_config() -> dict[str, Any]:
    """Load sites configuration from YAML."""
    config_path = Path(__file__).parent / "sites.yaml"
    logger.info("Loading sites config", path=str(config_path))
    with open(config_path) as f:
        config = yaml.safe_load(f)
    logger.info("Sites config loaded", num_sites=len(config.get("sites", {})))
    return config


class SiteInfo:
    """VEuPathDB site information."""

    def __init__(
        self,
        id: str,
        name: str,
        display_name: str,
        base_url: str,
        project_id: str,
        is_portal: bool,
    ) -> None:
        self.id = id
        self.name = name
        self.display_name = display_name
        self.base_url = base_url.rstrip("/")
        self.project_id = project_id
        self.is_portal = is_portal

    @property
    def service_url(self) -> str:
        """Get WDK service URL (already included in base_url from config)."""
        return self.base_url

    @property
    def web_base_url(self) -> str:
        """Get web UI base URL (strip /service if present)."""
        base = self.base_url.rstrip("/")
        if base.endswith("/service"):
            base = base[: -len("/service")]
        return base

    def strategy_url(self, strategy_id: int, root_step_id: int | None = None) -> str:
        """Build a strategy URL for the web UI."""
        if root_step_id is not None:
            return f"{self.web_base_url}/app/workspace/strategies/{strategy_id}/{root_step_id}"
        return f"{self.web_base_url}/app/workspace/strategies/{strategy_id}"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "displayName": self.display_name,
            "baseUrl": self.base_url,
            "projectId": self.project_id,
            "isPortal": self.is_portal,
        }


class SiteRouter:
    """Router for choosing appropriate VEuPathDB site."""

    def __init__(self) -> None:
        self._config = load_sites_config()
        self._sites: dict[str, SiteInfo] = {}
        self._clients: dict[str, VEuPathDBClient] = {}
        self._load_sites()

    def _load_sites(self) -> None:
        """Load site configurations."""
        sites_config = self._config.get("sites", {})
        logger.info("Loading sites", count=len(sites_config))
        for site_id, site_config in sites_config.items():
            try:
                self._sites[site_id] = SiteInfo(
                    id=site_id,
                    name=site_config["name"],
                    display_name=site_config["display_name"],
                    base_url=site_config["base_url"],
                    project_id=site_config["project_id"],
                    is_portal=site_config.get("is_portal", False),
                )
            except Exception as e:
                logger.error("Failed to load site", site_id=site_id, error=str(e))
        logger.info("Sites loaded", site_ids=list(self._sites.keys()))

    def get_site(self, site_id: str) -> SiteInfo:
        """Get site by ID."""
        logger.debug("Getting site", site_id=site_id, available=list(self._sites.keys()))
        if site_id not in self._sites:
            raise NotFoundError(
                code=ErrorCode.SITE_NOT_FOUND,
                title="Site not found",
                detail=f"Unknown site: {site_id}. Available: {list(self._sites.keys())}",
            )
        return self._sites[site_id]

    def list_sites(self) -> list[SiteInfo]:
        """List all available sites."""
        return list(self._sites.values())

    def get_default_site(self) -> SiteInfo:
        """Get the default site."""
        settings = get_settings()
        default_id = self._config.get("default_site", settings.veupathdb_default_site)
        return self.get_site(default_id)

    def get_client(self, site_id: str) -> VEuPathDBClient:
        """Get or create HTTP client for a site."""
        if site_id not in self._clients:
            site = self.get_site(site_id)
            routing = self._config.get("routing", {})
            settings = get_settings()
            timeout = (
                routing.get("portal_timeout", 120)
                if site.is_portal
                else routing.get("component_timeout", 30)
            )
            self._clients[site_id] = VEuPathDBClient(
                base_url=site.service_url,
                timeout=float(timeout),
                auth_token=settings.veupathdb_auth_token,
            )
        return self._clients[site_id]

    def get_portal_client(self) -> VEuPathDBClient:
        """Get client for the portal."""
        return self.get_client("veupathdb")

    def should_use_component(self, site_id: str) -> bool:
        """Check if component site should be used."""
        if site_id == "veupathdb":
            return False
        routing = self._config.get("routing", {})
        return routing.get("prefer_component", True)

    async def close_all(self) -> None:
        """Close all HTTP clients."""
        for client in self._clients.values():
            await client.close()
        self._clients.clear()


# Global router instance
_router: SiteRouter | None = None


def get_site_router() -> SiteRouter:
    """Get the global site router."""
    global _router
    if _router is None:
        _router = SiteRouter()
    return _router


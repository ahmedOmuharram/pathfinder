"""Site routing: choose portal vs component sites intelligently."""

from functools import lru_cache
from pathlib import Path
from typing import cast

import yaml

from veupath_chatbot.integrations.veupathdb.client import VEuPathDBClient
from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.errors import ErrorCode, NotFoundError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject

logger = get_logger(__name__)


@lru_cache
def load_sites_config() -> JSONObject:
    """Load sites configuration from YAML."""
    config_path = Path(__file__).parent / "sites.yaml"
    logger.info("Loading sites config", path=str(config_path))
    with open(config_path) as f:
        config = yaml.safe_load(f)
    logger.info(
        "Sites config loaded",
        num_sites=len(config.get("sites", {}) if isinstance(config, dict) else {}),
    )
    return cast(JSONObject, config)


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

    def to_dict(self) -> JSONObject:
        """Convert to dictionary."""
        return cast(
            JSONObject,
            {
                "id": self.id,
                "name": self.name,
                "displayName": self.display_name,
                "baseUrl": self.base_url,
                "projectId": self.project_id,
                "isPortal": self.is_portal,
            },
        )


class SiteRouter:
    """Router for choosing appropriate VEuPathDB site."""

    def __init__(self) -> None:
        self._config = load_sites_config()
        self._sites: dict[str, SiteInfo] = {}
        self._clients: dict[str, VEuPathDBClient] = {}
        self._load_sites()

    def _load_sites(self) -> None:
        """Load site configurations."""
        sites_config_raw = self._config.get("sites", {})
        if not isinstance(sites_config_raw, dict):
            logger.warning(
                "sites config is not a dict", type=type(sites_config_raw).__name__
            )
            return
        sites_config: JSONObject = sites_config_raw
        logger.info("Loading sites", count=len(sites_config))
        for site_id, site_config_raw in sites_config.items():
            if not isinstance(site_config_raw, dict):
                logger.warning(
                    "Site config is not a dict",
                    site_id=site_id,
                    type=type(site_config_raw).__name__,
                )
                continue
            site_config: JSONObject = site_config_raw
            try:
                name_raw = site_config.get("name")
                display_name_raw = site_config.get("display_name")
                base_url_raw = site_config.get("base_url")
                project_id_raw = site_config.get("project_id")
                is_portal_raw = site_config.get("is_portal", False)

                name = str(name_raw) if name_raw is not None else ""
                display_name = (
                    str(display_name_raw) if display_name_raw is not None else ""
                )
                base_url = str(base_url_raw) if base_url_raw is not None else ""
                project_id = str(project_id_raw) if project_id_raw is not None else ""
                is_portal = (
                    bool(is_portal_raw) if isinstance(is_portal_raw, bool) else False
                )

                self._sites[site_id] = SiteInfo(
                    id=site_id,
                    name=name,
                    display_name=display_name,
                    base_url=base_url,
                    project_id=project_id,
                    is_portal=is_portal,
                )
            except Exception as e:
                logger.error("Failed to load site", site_id=site_id, error=str(e))
        logger.info("Sites loaded", site_ids=list(self._sites.keys()))

    def get_site(self, site_id: str) -> SiteInfo:
        """Get site by ID."""
        logger.debug(
            "Getting site", site_id=site_id, available=list(self._sites.keys())
        )
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
        default_id_raw = self._config.get(
            "default_site", settings.veupathdb_default_site
        )
        default_id = (
            str(default_id_raw)
            if default_id_raw is not None
            else settings.veupathdb_default_site
        )
        return self.get_site(default_id)

    def get_client(self, site_id: str) -> VEuPathDBClient:
        """Get or create HTTP client for a site."""
        if site_id not in self._clients:
            site = self.get_site(site_id)
            routing_raw = self._config.get("routing", {})
            if not isinstance(routing_raw, dict):
                routing: JSONObject = {}
            else:
                routing = routing_raw
            settings = get_settings()
            portal_timeout_raw = routing.get("portal_timeout", 120)
            component_timeout_raw = routing.get("component_timeout", 30)
            portal_timeout = (
                float(portal_timeout_raw)
                if isinstance(portal_timeout_raw, (int, float))
                else 120.0
            )
            component_timeout = (
                float(component_timeout_raw)
                if isinstance(component_timeout_raw, (int, float))
                else 30.0
            )
            timeout = portal_timeout if site.is_portal else component_timeout
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
        routing_raw = self._config.get("routing", {})
        if not isinstance(routing_raw, dict):
            return True
        routing: JSONObject = routing_raw
        prefer_component_raw = routing.get("prefer_component", True)
        return (
            bool(prefer_component_raw)
            if isinstance(prefer_component_raw, bool)
            else True
        )

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

"""Site routing: choose portal vs component sites intelligently."""

import threading
from functools import lru_cache
from pathlib import Path
from typing import cast

import yaml
from pydantic import BaseModel, Field

from veupath_chatbot.integrations.veupathdb.client import VEuPathDBClient
from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.errors import ErrorCode, NotFoundError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject

logger = get_logger(__name__)


# ── Pydantic config models ───────────────────────────────────────────


class SiteConfig(BaseModel):
    """Validated configuration for a single VEuPathDB site."""

    name: str = ""
    display_name: str = ""
    base_url: str = ""
    project_id: str = ""
    is_portal: bool = False


class RoutingConfig(BaseModel):
    """Validated routing/timeout configuration."""

    portal_timeout: float = 120.0
    component_timeout: float = 30.0


class SitesConfig(BaseModel):
    """Top-level sites configuration parsed from YAML."""

    sites: dict[str, SiteConfig] = Field(default_factory=dict)
    default_site: str = "veupathdb"
    routing: RoutingConfig = Field(default_factory=RoutingConfig)


@lru_cache
def load_sites_config(config_path: str | None = None) -> SitesConfig:
    """Load and validate sites configuration from YAML.

    :param config_path: Optional path to a YAML file. If unset or empty, uses
        the bundled ``sites.yaml`` next to this module.
    :returns: Validated SitesConfig model.
    """
    path = (
        Path(config_path).resolve()
        if (config_path and config_path.strip())
        else Path(__file__).parent / "sites.yaml"
    )
    logger.info("Loading sites config", path=str(path))
    with open(path) as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict):
        logger.warning("Sites config is not a dict, using defaults")
        return SitesConfig()
    config = SitesConfig.model_validate(raw)
    logger.info("Sites config loaded", num_sites=len(config.sites))
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

    @classmethod
    def from_config(cls, site_id: str, cfg: SiteConfig) -> SiteInfo:
        """Construct a SiteInfo from a validated SiteConfig."""
        return cls(
            id=site_id,
            name=cfg.name,
            display_name=cfg.display_name,
            base_url=cfg.base_url,
            project_id=cfg.project_id,
            is_portal=cfg.is_portal,
        )

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
        """Build a strategy URL for the web UI.

        :param strategy_id: WDK strategy ID.
        :param root_step_id: Root step ID (default: None).

        """
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
        settings = get_settings()
        self._config = load_sites_config(settings.veupathdb_sites_config)
        self._sites: dict[str, SiteInfo] = {}
        self._clients: dict[str, VEuPathDBClient] = {}
        self._client_lock = threading.Lock()
        self._load_sites()

    def _load_sites(self) -> None:
        """Load site configurations from validated config."""
        logger.info("Loading sites", count=len(self._config.sites))
        for site_id, site_cfg in self._config.sites.items():
            self._sites[site_id] = SiteInfo.from_config(site_id, site_cfg)
        logger.info("Sites loaded", site_ids=list(self._sites.keys()))

    def get_site(self, site_id: str) -> SiteInfo:
        """Get site by ID.

        :param site_id: VEuPathDB site identifier.

        """
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
        default_id = self._config.default_site or settings.veupathdb_default_site
        return self.get_site(default_id)

    def get_client(self, site_id: str) -> VEuPathDBClient:
        """Get or create HTTP client for a site.

        :param site_id: VEuPathDB site identifier.

        """
        if site_id in self._clients:
            return self._clients[site_id]
        with self._client_lock:
            if site_id not in self._clients:
                site = self.get_site(site_id)
                routing = self._config.routing
                settings = get_settings()
                timeout = (
                    routing.portal_timeout
                    if site.is_portal
                    else routing.component_timeout
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

    async def close_all(self) -> None:
        """Close all HTTP clients."""
        for client in self._clients.values():
            await client.close()
        self._clients.clear()


# Global router instance
_router: SiteRouter | None = None
_router_lock = threading.Lock()


def get_site_router() -> SiteRouter:
    """Get the global site router."""
    global _router
    if _router is not None:
        return _router
    with _router_lock:
        if _router is None:
            _router = SiteRouter()
        return _router

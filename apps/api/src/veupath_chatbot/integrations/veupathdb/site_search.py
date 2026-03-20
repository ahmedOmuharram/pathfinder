"""Integration for VEuPathDB "site search" service.

This is the same backend used by the web UI route `/app/search`.

Important: this service is hosted at the site origin root (e.g. https://plasmodb.org/site-search),
not under the WDK service prefix (e.g. https://plasmodb.org/plasmo/service).

The site-search endpoint is **GET-only** -- POST returns HTTP 500.  Parameters
are passed as query-string key-value pairs:

  ``searchText``           -- search query
  ``docType``              -- restrict to a document type (e.g. "gene", "search")
  ``offset`` / ``numRecords`` -- pagination
  ``restrictToProject``    -- site project id filter
  ``restrictSearchToOrganisms`` -- comma-separated organism names
"""

import re
from urllib.parse import urlparse

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from veupath_chatbot.integrations.veupathdb.site_router import get_site_router
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject

logger = get_logger(__name__)

# Shared client for site-search requests (avoids connection-per-request overhead).
_site_search_client_holder: dict[str, httpx.AsyncClient] = {}


def _get_site_search_client() -> httpx.AsyncClient:
    """Get or create the shared site-search HTTP client."""
    existing = _site_search_client_holder.get("v")
    if existing is None or existing.is_closed:
        _site_search_client_holder["v"] = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, read=90.0),
            follow_redirects=True,
            headers={"Accept": "application/json"},
        )
    return _site_search_client_holder["v"]


async def close_site_search_client() -> None:
    """Close the shared site-search HTTP client (call during app shutdown)."""
    client = _site_search_client_holder.pop("v", None)
    if client is not None and not client.is_closed:
        await client.aclose()


def strip_html_tags(value: str) -> str:
    # site-search highlights matches with <em> tags.
    return re.sub(r"</?[^>]+>", "", value or "").strip()


@retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
)
async def query_site_search(
    site_id: str,
    *,
    search_text: str,
    document_type: str | None = None,
    organisms: list[str] | None = None,
    limit: int = 20,
    offset: int = 0,
) -> JSONObject:
    """Query the site's /site-search endpoint and return parsed JSON.

    The VEuPathDB site-search service only accepts GET requests with
    query-string parameters.  POST returns HTTP 500.

    :param organisms: Optional organism names to restrict results to.
    """
    router = get_site_router()
    site = router.get_site(site_id)

    # site-search is hosted at the site origin, not under the WDK service path.
    parsed = urlparse(site.base_url)
    url = f"{parsed.scheme}://{parsed.netloc}/site-search"

    params: dict[str, str] = {
        "searchText": search_text or "",
        "offset": str(int(offset)),
        "numRecords": str(int(limit)),
        "restrictToProject": site.project_id,
    }
    if document_type:
        params["docType"] = document_type
    if organisms:
        params["restrictSearchToOrganisms"] = ",".join(organisms)

    client = _get_site_search_client()
    resp = await client.get(url, params=params)
    resp.raise_for_status()
    return resp.json() if resp.content else {}

"""Integration for VEuPathDB "site search" service.

This is the same backend used by the web UI route `/app/search`.

Important: this service is hosted at the site origin root (e.g. https://plasmodb.org/site-search),
not under the WDK service prefix (e.g. https://plasmodb.org/plasmo/service).
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from veupath_chatbot.integrations.veupathdb.site_router import get_site_router
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject

logger = get_logger(__name__)


def strip_html_tags(value: str) -> str:
    # site-search highlights matches with <em> tags.
    return re.sub(r"</?[^>]+>", "", value or "").strip()


async def query_site_search(
    site_id: str,
    *,
    search_text: str,
    document_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> JSONObject:
    """Query the site's /site-search endpoint and return parsed JSON."""
    router = get_site_router()
    site = router.get_site(site_id)

    parsed = urlparse(site.base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    url = f"{origin}/site-search"

    payload: JSONObject = {
        "searchText": search_text or "",
        "pagination": {"offset": int(offset), "numRecords": int(limit)},
        "restrictToProject": site.project_id,
    }
    if document_type:
        payload["documentTypeFilter"] = {"documentType": document_type}

    import httpx

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(30.0), follow_redirects=True
    ) as client:
        resp = await client.post(
            url,
            json=payload,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        return resp.json() if resp.content else {}

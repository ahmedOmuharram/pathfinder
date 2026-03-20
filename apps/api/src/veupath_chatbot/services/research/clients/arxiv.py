"""arXiv API client."""

import re

import httpx

from veupath_chatbot.platform.errors import ExternalServiceError
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.research.clients._base import (
    API_USER_AGENT,
    StandardClient,
    make_citation,
)
from veupath_chatbot.services.research.utils import strip_tags, truncate_text


class ArxivClient(StandardClient):
    """Client for arXiv API."""

    _source_name = "arxiv"

    async def _fetch_raw(self, query: str, *, limit: int) -> list[JSONValue]:
        url = "http://export.arxiv.org/api/query"
        params = {
            "search_query": f"all:{query}",
            "start": "0",
            "max_results": str(limit),
        }
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, headers={"User-Agent": API_USER_AGENT}
            ) as client:
                resp = await client.get(url, params=params, follow_redirects=True)
                resp.raise_for_status()
                xml = resp.text or ""
        except httpx.HTTPError as exc:
            service = "arXiv"
            raise ExternalServiceError(service, str(exc)) from exc
        entries = re.findall(
            r"<entry>(.*?)</entry>", xml, flags=re.IGNORECASE | re.DOTALL
        )
        return [{"_xml": e} for e in entries[:limit]]

    def _parse_item(
        self, raw: JSONValue, *, abstract_max_chars: int
    ) -> tuple[JSONObject, JSONObject] | None:
        if not isinstance(raw, dict):
            return None
        e = raw.get("_xml")
        if not isinstance(e, str):
            return None

        title = strip_tags(
            "".join(
                re.findall(r"<title>(.*?)</title>", e, flags=re.IGNORECASE | re.DOTALL)
            )
        ).strip()
        link_m = re.search(r'<link[^>]+href="([^"]+)"', e, flags=re.IGNORECASE)
        url_item = link_m.group(1) if link_m else None
        abstract = strip_tags(
            "".join(
                re.findall(
                    r"<summary>(.*?)</summary>", e, flags=re.IGNORECASE | re.DOTALL
                )
            )
        ).strip()

        result: JSONObject = {
            "title": title,
            "url": url_item,
            "abstract": truncate_text(abstract, abstract_max_chars) or "",
            "snippet": abstract,
        }
        citation = make_citation(
            source="arxiv",
            id_prefix="arxiv",
            title=title or (url_item or "arXiv result"),
            url=url_item,
            snippet=abstract,
        )
        return result, citation

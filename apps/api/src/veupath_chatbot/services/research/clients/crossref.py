"""Crossref API client."""

import httpx

from veupath_chatbot.domain.research.citations import (
    Citation,
    _new_citation_id,
    _now_iso,
)
from veupath_chatbot.domain.research.papers import CrossRefRawWork
from veupath_chatbot.platform.errors import ExternalServiceError
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.research.clients._base import StandardClient


class CrossrefClient(StandardClient):
    """Client for Crossref API."""

    _source_name = "crossref"

    async def _fetch_raw(self, query: str, *, limit: int) -> list[JSONValue]:
        url = "https://api.crossref.org/works"
        params = {"query": query, "rows": str(limit)}
        headers = {"User-Agent": "pathfinder-planner/1.0 (mailto:unknown@example.com)"}
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, headers=headers
            ) as client:
                resp = await client.get(url, params=params, follow_redirects=True)
                resp.raise_for_status()
                payload = resp.json()
        except httpx.HTTPError as exc:
            service = "CrossRef"
            raise ExternalServiceError(service, str(exc)) from exc
        items = (
            payload.get("message", {}).get("items", [])
            if isinstance(payload, dict)
            else []
        )
        return list(items)

    def _parse_item(
        self, raw: JSONValue, *, abstract_max_chars: int
    ) -> tuple[JSONObject, JSONObject] | None:
        if not isinstance(raw, dict):
            return None

        parsed = CrossRefRawWork.model_validate(raw).to_parsed_paper()

        result = parsed.model_dump(by_alias=True, mode="json")
        citation = Citation(
            id=_new_citation_id("crossref"),
            source="crossref",
            title=parsed.title or (parsed.url or "Crossref result"),
            url=parsed.url,
            authors=parsed.authors or None,
            year=parsed.year,
            doi=parsed.doi,
            snippet=parsed.journal_title,
            accessed_at=_now_iso(),
        ).model_dump(by_alias=True, exclude_none=True, mode="json")
        return result, citation

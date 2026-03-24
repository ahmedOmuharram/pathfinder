"""OpenAlex API client."""

import httpx

from veupath_chatbot.domain.research.citations import (
    Citation,
    _new_citation_id,
    _now_iso,
)
from veupath_chatbot.domain.research.papers import OpenAlexRawWork
from veupath_chatbot.platform.errors import ExternalServiceError
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.research.clients._base import (
    API_USER_AGENT,
    StandardClient,
)
from veupath_chatbot.services.research.utils import truncate_text


class OpenAlexClient(StandardClient):
    """Client for OpenAlex API."""

    _source_name = "openalex"

    async def _fetch_raw(self, query: str, *, limit: int) -> list[JSONValue]:
        url = "https://api.openalex.org/works"
        params = {"search": query, "per-page": str(limit)}
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, headers={"User-Agent": API_USER_AGENT}
            ) as client:
                resp = await client.get(url, params=params, follow_redirects=True)
                resp.raise_for_status()
                payload = resp.json()
        except httpx.HTTPError as exc:
            service = "OpenAlex"
            raise ExternalServiceError(service, str(exc)) from exc
        items = payload.get("results", []) if isinstance(payload, dict) else []
        return list(items)

    def _parse_item(
        self, raw: JSONValue, *, abstract_max_chars: int
    ) -> tuple[JSONObject, JSONObject] | None:
        if not isinstance(raw, dict):
            return None

        parsed = OpenAlexRawWork.model_validate(raw).to_parsed_paper()
        parsed.abstract = truncate_text(parsed.abstract, abstract_max_chars)
        parsed.snippet = parsed.abstract or parsed.journal_title

        result = parsed.model_dump(by_alias=True, mode="json")
        citation = Citation(
            id=_new_citation_id("openalex"),
            source="openalex",
            title=parsed.title or (parsed.url or "OpenAlex result"),
            url=parsed.url,
            authors=parsed.authors or None,
            year=parsed.year,
            doi=parsed.doi,
            snippet=parsed.abstract or parsed.journal_title,
            accessed_at=_now_iso(),
        ).model_dump(by_alias=True, exclude_none=True, mode="json")
        return result, citation

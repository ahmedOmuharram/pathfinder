"""Semantic Scholar API client."""

import asyncio
import os

import httpx

from veupath_chatbot.domain.research.citations import (
    Citation,
    _new_citation_id,
    _now_iso,
)
from veupath_chatbot.domain.research.papers import SemanticScholarRawPaper
from veupath_chatbot.platform.errors import ExternalServiceError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.research.clients._base import (
    API_USER_AGENT,
    StandardClient,
)
from veupath_chatbot.services.research.utils import truncate_text

logger = get_logger(__name__)

_MAX_RETRIES = 3
_BACKOFF_BASE_S = 1.0


class SemanticScholarClient(StandardClient):
    """Client for Semantic Scholar API."""

    _source_name = "semanticscholar"

    async def _fetch_raw(self, query: str, *, limit: int) -> list[JSONValue]:
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            "query": query,
            "limit": str(limit),
            "fields": "title,year,authors,url,abstract,journal,externalIds",
        }
        headers: dict[str, str] = {"User-Agent": API_USER_AGENT}
        api_key = os.environ.get("S2_API_KEY")
        if api_key:
            headers["x-api-key"] = api_key

        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                async with httpx.AsyncClient(
                    timeout=self._timeout, headers=headers
                ) as client:
                    resp = await client.get(url, params=params, follow_redirects=True)
                    if resp.status_code == 429:
                        wait = _BACKOFF_BASE_S * (2 ** attempt)
                        logger.warning(
                            "Semantic Scholar 429, retrying",
                            attempt=attempt + 1,
                            wait_s=wait,
                        )
                        await asyncio.sleep(wait)
                        continue
                    resp.raise_for_status()
                    payload = resp.json()
                    items = payload.get("data", []) if isinstance(payload, dict) else []
                    return list(items)
            except httpx.HTTPError as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES - 1:
                    wait = _BACKOFF_BASE_S * (2 ** attempt)
                    logger.warning(
                        "Semantic Scholar request failed, retrying",
                        attempt=attempt + 1,
                        wait_s=wait,
                        error=str(exc),
                    )
                    await asyncio.sleep(wait)

        raise ExternalServiceError("Semantic Scholar", str(last_exc))

    def _parse_item(
        self, raw: JSONValue, *, abstract_max_chars: int
    ) -> tuple[JSONObject, JSONObject] | None:
        if not isinstance(raw, dict):
            return None

        parsed = SemanticScholarRawPaper.model_validate(raw).to_parsed_paper()
        parsed.abstract = truncate_text(parsed.abstract, abstract_max_chars)
        parsed.snippet = parsed.abstract or parsed.journal_title

        result = parsed.model_dump(by_alias=True, mode="json")
        citation = Citation(
            id=_new_citation_id("s2"),
            source="semanticscholar",
            title=parsed.title or (parsed.url or "Semantic Scholar result"),
            url=parsed.url,
            authors=parsed.authors or None,
            year=parsed.year,
            doi=parsed.doi,
            pmid=parsed.pmid,
            snippet=parsed.abstract or parsed.journal_title,
            accessed_at=_now_iso(),
        ).model_dump(by_alias=True, exclude_none=True, mode="json")
        return result, citation

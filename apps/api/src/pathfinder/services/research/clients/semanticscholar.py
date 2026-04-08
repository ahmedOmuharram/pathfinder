"""Semantic Scholar API client."""

import os

import httpx

from pathfinder.domain.research.citations import (
    Citation,
    _new_citation_id,
    _now_iso,
)
from pathfinder.domain.research.papers import ParsedPaper, SemanticScholarRawPaper
from pathfinder.platform.errors import ExternalServiceError
from pathfinder.platform.types import JSONValue
from pathfinder.services.research.clients._base import (
    API_USER_AGENT,
    StandardClient,
)
from pathfinder.services.research.utils import truncate_text


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

        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, headers=headers
            ) as client:
                resp = await client.get(url, params=params, follow_redirects=True)
                resp.raise_for_status()
                payload = resp.json()
        except httpx.HTTPError as exc:
            service = "Semantic Scholar"
            raise ExternalServiceError(service, str(exc)) from exc
        items = payload.get("data", []) if isinstance(payload, dict) else []
        return list(items)

    def _parse_item(
        self, raw: JSONValue, *, abstract_max_chars: int
    ) -> tuple[ParsedPaper, Citation] | None:
        if not isinstance(raw, dict):
            return None

        parsed = SemanticScholarRawPaper.model_validate(raw).to_parsed_paper()
        parsed.abstract = truncate_text(parsed.abstract, abstract_max_chars)
        parsed.snippet = parsed.abstract or parsed.journal_title

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
        )
        return parsed, citation

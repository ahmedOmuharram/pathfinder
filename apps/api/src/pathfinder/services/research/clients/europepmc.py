"""Europe PMC API client."""

import httpx

from pathfinder.domain.research.citations import (
    Citation,
    _new_citation_id,
    _now_iso,
)
from pathfinder.domain.research.papers import EuropePmcRawResult, ParsedPaper
from pathfinder.platform.errors import ExternalServiceError
from pathfinder.platform.types import JSONValue
from pathfinder.services.research.clients._base import (
    API_USER_AGENT,
    StandardClient,
)
from pathfinder.services.research.utils import truncate_text


class EuropePmcClient(StandardClient):
    """Client for Europe PMC API."""

    _source_name = "europepmc"

    async def _fetch_raw(self, query: str, *, limit: int) -> list[JSONValue]:
        url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        params = {
            "query": query,
            "format": "json",
            "pageSize": str(limit),
            "resultType": "core",
        }
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, headers={"User-Agent": API_USER_AGENT}
            ) as client:
                resp = await client.get(url, params=params, follow_redirects=True)
                resp.raise_for_status()
                payload = resp.json()
        except httpx.HTTPError as exc:
            service = "EuropePMC"
            raise ExternalServiceError(service, str(exc)) from exc
        hits = (
            payload.get("resultList", {}).get("result", [])
            if isinstance(payload, dict)
            else []
        )
        return list(hits)

    def _parse_item(
        self, raw: JSONValue, *, abstract_max_chars: int
    ) -> tuple[ParsedPaper, Citation] | None:
        if not isinstance(raw, dict):
            return None

        parsed = EuropePmcRawResult.model_validate(raw).to_parsed_paper()
        parsed.abstract = truncate_text(parsed.abstract, abstract_max_chars)

        citation = Citation(
            id=_new_citation_id("epmc"),
            source="europepmc",
            title=parsed.title or (parsed.url or "Europe PMC result"),
            url=parsed.url,
            authors=parsed.authors or None,
            year=parsed.year,
            doi=parsed.doi,
            pmid=parsed.pmid,
            snippet=parsed.abstract or parsed.journal_title,
            accessed_at=_now_iso(),
        )
        return parsed, citation

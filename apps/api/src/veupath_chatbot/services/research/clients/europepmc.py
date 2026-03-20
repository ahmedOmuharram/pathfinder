"""Europe PMC API client."""

from typing import cast

import httpx

from veupath_chatbot.domain.research.citations import (
    Citation,
    _new_citation_id,
    _now_iso,
)
from veupath_chatbot.platform.errors import ExternalServiceError
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.research.clients._base import (
    API_USER_AGENT,
    StandardClient,
)
from veupath_chatbot.services.research.utils import truncate_text


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
    ) -> tuple[JSONObject, JSONObject] | None:
        if not isinstance(raw, dict):
            return None
        item = raw

        title_raw = item.get("title")
        title = title_raw.strip() if isinstance(title_raw, str) else ""

        year_i: int | None
        try:
            pub_year = item.get("pubYear")
            if pub_year is not None and isinstance(pub_year, (int, str)):
                if isinstance(pub_year, str) and pub_year.isdigit():
                    year_i = int(pub_year)
                elif isinstance(pub_year, int):
                    year_i = pub_year
                else:
                    year_i = None
            else:
                year_i = None
        except ValueError, TypeError:
            year_i = None

        doi_val = item.get("doi")
        doi: str | None = doi_val if isinstance(doi_val, str) else None
        pmid_val = item.get("pmid")
        pmid: str | None = pmid_val if isinstance(pmid_val, str) else None
        author_str = item.get("authorString")
        authors = (
            [a.strip() for a in author_str.split(",") if a.strip()]
            if isinstance(author_str, str)
            else None
        )
        journal = item.get("journalTitle")
        journal = journal.strip() if isinstance(journal, str) else None

        link: str | None = None
        if doi:
            link = f"https://doi.org/{doi}"
        elif pmid:
            link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

        abstract = item.get("abstractText")
        abstract = truncate_text(
            abstract if isinstance(abstract, str) else None, abstract_max_chars
        )

        result: JSONObject = {
            "title": title,
            "year": year_i,
            "doi": doi,
            "pmid": pmid,
            "url": link,
            "authors": cast("JSONValue", authors),
            "journalTitle": journal,
            "abstract": abstract,
            "snippet": journal,
        }
        citation = Citation(
            id=_new_citation_id("epmc"),
            source="europepmc",
            title=title or (link or "Europe PMC result"),
            url=link,
            authors=authors,
            year=year_i,
            doi=doi,
            pmid=pmid,
            snippet=abstract or journal,
            accessed_at=_now_iso(),
        ).to_dict()
        return result, citation

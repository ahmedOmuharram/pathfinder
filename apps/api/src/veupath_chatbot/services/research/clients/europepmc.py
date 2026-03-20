"""Europe PMC API client."""

from typing import cast

import httpx

from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.research.clients._base import (
    API_USER_AGENT,
    StandardClient,
    make_citation,
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
        async with httpx.AsyncClient(
            timeout=self._timeout, headers={"User-Agent": API_USER_AGENT}
        ) as client:
            resp = await client.get(url, params=params, follow_redirects=True)
            resp.raise_for_status()
            payload = resp.json()
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
        except Exception:
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
        citation = make_citation(
            source="europepmc",
            id_prefix="epmc",
            title=title or (link or "Europe PMC result"),
            url=link,
            authors=authors,
            year=year_i,
            doi=doi,
            pmid=pmid,
            snippet=abstract or journal,
        )
        return result, citation

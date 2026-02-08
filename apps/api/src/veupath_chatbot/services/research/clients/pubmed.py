"""PubMed API client."""

from __future__ import annotations

import re as _re
from typing import cast

import httpx

from veupath_chatbot.domain.research.citations import (
    Citation,
    _new_citation_id,
    _now_iso,
    ensure_unique_citation_tags,
)
from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue
from veupath_chatbot.services.research.utils import strip_tags, truncate_text


class PubmedClient:
    """Client for PubMed API."""

    def __init__(self, *, timeout_seconds: float = 15.0) -> None:
        self._timeout = timeout_seconds

    async def search(
        self,
        query: str,
        *,
        limit: int,
        include_abstract: bool,
        abstract_max_chars: int,
    ) -> JSONObject:
        """Search PubMed."""
        headers = {
            "User-Agent": "pathfinder-planner/1.0 (+https://pathfinder.veupathdb.org)"
        }
        async with httpx.AsyncClient(timeout=self._timeout, headers=headers) as client:
            esearch = await client.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                params={
                    "db": "pubmed",
                    "term": query,
                    "retmax": str(limit),
                    "retmode": "json",
                },
            )
            esearch.raise_for_status()
            search_payload = esearch.json()
            idlist = (
                (search_payload.get("esearchresult") or {}).get("idlist") or []
                if isinstance(search_payload, dict)
                else []
            )
            pmids = [str(x) for x in idlist if str(x).strip()]
            if not pmids:
                return {
                    "query": query,
                    "source": "pubmed",
                    "results": [],
                    "citations": [],
                }

            esummary = await client.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
                params={"db": "pubmed", "id": ",".join(pmids), "retmode": "json"},
            )
            esummary.raise_for_status()
            sum_payload = esummary.json()
            sum_result = (
                sum_payload.get("result") if isinstance(sum_payload, dict) else {}
            )

            abstracts_by_pmid: dict[str, str] = {}
            if include_abstract:
                efetch = await client.get(
                    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
                    params={"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"},
                )
                efetch.raise_for_status()
                xml = efetch.text or ""
                # Minimal extraction (sufficient for unit tests).
                for pmid in pmids:
                    m = _re.search(
                        rf"<PMID>{_re.escape(pmid)}</PMID>.*?<Abstract>.*?<AbstractText[^>]*>(.*?)</AbstractText>",
                        xml,
                        flags=_re.IGNORECASE | _re.DOTALL,
                    )
                    if m:
                        abstracts_by_pmid[pmid] = strip_tags(m.group(1))

        results: JSONArray = []
        citations: list[JSONObject] = []
        for pmid in pmids:
            meta = sum_result.get(pmid) if isinstance(sum_result, dict) else None
            if not isinstance(meta, dict):
                continue
            title = str(meta.get("title") or "").strip()
            pubdate = str(meta.get("pubdate") or "")
            year = None
            m_year = _re.search(r"(\d{4})", pubdate)
            if m_year:
                try:
                    year = int(m_year.group(1))
                except Exception:
                    year = None
            authors = None
            raw_authors = meta.get("authors")
            if isinstance(raw_authors, list):
                authors = [
                    str(a.get("name"))
                    for a in raw_authors
                    if isinstance(a, dict) and a.get("name")
                ]
            journal = meta.get("fulljournalname")
            journal = str(journal).strip() if journal else None
            abstract = abstracts_by_pmid.get(pmid)
            abstract = (
                truncate_text(abstract, abstract_max_chars)
                if include_abstract
                else None
            )

            url_item = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            results.append(
                {
                    "title": title,
                    "year": year,
                    "pmid": pmid,
                    "url": url_item,
                    "authors": cast(JSONValue, authors),
                    "journalTitle": journal,
                    "abstract": abstract,
                    "snippet": abstract or journal,
                }
            )
            citations.append(
                Citation(
                    id=_new_citation_id("pubmed"),
                    source="pubmed",
                    title=title or url_item,
                    url=url_item,
                    authors=authors,
                    year=year,
                    pmid=pmid,
                    snippet=abstract or journal,
                    accessed_at=_now_iso(),
                ).to_dict()
            )
        ensure_unique_citation_tags(citations)
        return {
            "query": query,
            "source": "pubmed",
            "results": results,
            "citations": cast(JSONValue, citations),
        }

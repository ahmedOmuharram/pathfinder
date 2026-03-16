"""PubMed API client."""

import re
from typing import cast

import httpx

from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.research.clients._base import (
    API_USER_AGENT,
    BaseClient,
    build_response,
    make_citation,
)
from veupath_chatbot.services.research.utils import strip_tags, truncate_text


class PubmedClient(BaseClient):
    """Client for PubMed API.

    PubMed requires a multi-step fetch (esearch -> esummary -> optional
    efetch for abstracts), so it keeps a custom ``search`` method.
    Per-item parsing still goes through ``_parse_item`` / ``_build_results``.
    """

    _include_abstract: bool = False

    async def search(
        self,
        query: str,
        *,
        limit: int,
        include_abstract: bool,
        abstract_max_chars: int,
    ) -> JSONObject:
        """Search PubMed."""
        raw_items = await self._fetch_raw(
            query,
            limit=limit,
            include_abstract=include_abstract,
        )
        if not raw_items:
            return build_response(
                query=query, source="pubmed", results=[], citations=[]
            )
        self._include_abstract = include_abstract
        results, citations = self._build_results(
            raw_items, abstract_max_chars=abstract_max_chars
        )
        return build_response(
            query=query, source="pubmed", results=results, citations=citations
        )

    # -- fetch -------------------------------------------------------------

    async def _fetch_raw(
        self, query: str, *, limit: int, include_abstract: bool
    ) -> list[JSONValue]:
        """esearch + esummary (+ optional efetch) -> list of per-PMID dicts."""
        async with httpx.AsyncClient(
            timeout=self._timeout, headers={"User-Agent": API_USER_AGENT}
        ) as client:
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
                return []

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
                for pmid in pmids:
                    m = re.search(
                        rf"<PMID>{re.escape(pmid)}</PMID>.*?<Abstract>.*?<AbstractText[^>]*>(.*?)</AbstractText>",
                        xml,
                        flags=re.IGNORECASE | re.DOTALL,
                    )
                    if m:
                        abstracts_by_pmid[pmid] = strip_tags(m.group(1))

        items: list[JSONValue] = []
        for pmid in pmids:
            meta = sum_result.get(pmid) if isinstance(sum_result, dict) else None
            if not isinstance(meta, dict):
                continue
            items.append(
                {
                    "_pmid": pmid,
                    "_meta": meta,
                    "_abstract": abstracts_by_pmid.get(pmid),
                }
            )
        return items

    # -- parse -------------------------------------------------------------

    def _parse_item(
        self, raw: JSONValue, *, abstract_max_chars: int
    ) -> tuple[JSONObject, JSONObject] | None:
        if not isinstance(raw, dict):
            return None
        pmid = raw.get("_pmid")
        meta = raw.get("_meta")
        if not isinstance(pmid, str) or not isinstance(meta, dict):
            return None

        title = str(meta.get("title") or "").strip()
        pubdate = str(meta.get("pubdate") or "")
        year: int | None = None
        m_year = re.search(r"(\d{4})", pubdate)
        if m_year:
            try:
                year = int(m_year.group(1))
            except Exception:
                year = None

        authors: list[str] | None = None
        raw_authors = meta.get("authors")
        if isinstance(raw_authors, list):
            authors = [
                str(a.get("name"))
                for a in raw_authors
                if isinstance(a, dict) and a.get("name")
            ]

        journal = meta.get("fulljournalname")
        journal = str(journal).strip() if journal else None

        abstract_text = raw.get("_abstract")
        abstract: str | None = abstract_text if isinstance(abstract_text, str) else None
        abstract = (
            truncate_text(abstract, abstract_max_chars)
            if self._include_abstract
            else None
        )

        url_item = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

        result: JSONObject = {
            "title": title,
            "year": year,
            "pmid": pmid,
            "url": url_item,
            "authors": cast(JSONValue, authors),
            "journalTitle": journal,
            "abstract": abstract,
            "snippet": abstract or journal,
        }
        citation = make_citation(
            source="pubmed",
            id_prefix="pubmed",
            title=title or url_item,
            url=url_item,
            authors=authors,
            year=year,
            pmid=pmid,
            snippet=abstract or journal,
        )
        return result, citation

"""Research tools for planning mode (web + literature) with citations."""

from __future__ import annotations

import asyncio
import html as _html
import re as _re
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from string import ascii_lowercase
from typing import Any, Literal
from urllib.parse import parse_qs, unquote, urlparse
from uuid import uuid4

import httpx


CitationSource = Literal[
    "web",
    "europepmc",
    "crossref",
    "openalex",
    "semanticscholar",
    "pubmed",
    "arxiv",
    "biorxiv",
    "medrxiv",
]
LiteratureSource = Literal[
    "europepmc",
    "crossref",
    "openalex",
    "semanticscholar",
    "pubmed",
    "arxiv",
    "biorxiv",
    "medrxiv",
    "all",
]
LiteratureSort = Literal["relevance", "newest"]


@dataclass(frozen=True)
class Citation:
    id: str
    source: CitationSource
    title: str
    url: str | None = None
    authors: list[str] | None = None
    year: int | None = None
    doi: str | None = None
    pmid: str | None = None
    snippet: str | None = None
    accessed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        tag = _suggest_citation_tag(
            source=self.source,
            title=self.title,
            authors=self.authors,
            year=self.year,
            doi=self.doi,
            pmid=self.pmid,
            url=self.url,
        )
        return {
            "id": self.id,
            "source": self.source,
            "tag": tag,
            "title": self.title,
            "url": self.url,
            "authors": self.authors,
            "year": self.year,
            "doi": self.doi,
            "pmid": self.pmid,
            "snippet": self.snippet,
            "accessedAt": self.accessed_at,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_citation_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _slug_token(value: str | None, *, max_len: int = 32) -> str:
    if not isinstance(value, str):
        return ""
    t = value.strip().lower()
    if not t:
        return ""
    t = _re.sub(r"[^a-z0-9]+", "", t)
    return t[:max_len]


def _suggest_citation_tag(
    *,
    source: CitationSource,
    title: str,
    authors: list[str] | None,
    year: int | None,
    doi: str | None,
    pmid: str | None,
    url: str | None,
) -> str:
    first_author = (authors or [None])[0]
    first_last = (
        _slug_token(str(first_author).split(",")[0].split()[0]) if first_author else ""
    )
    if first_last and year:
        return f"{first_last}{year}"
    if first_last:
        return first_last

    first_word = _slug_token(title.split()[0]) if isinstance(title, str) and title.split() else ""
    if first_word and year:
        return f"{first_word}{year}"

    title_slug = _slug_token(title, max_len=20)
    if title_slug:
        return title_slug

    stable = _slug_token(doi or pmid or url, max_len=20)
    return stable or str(source)


def _ensure_unique_citation_tags(citations: list[dict[str, Any]]) -> None:
    used: dict[str, int] = {}
    for c in citations:
        if not isinstance(c, dict):
            continue
        base = _slug_token(str(c.get("tag") or ""), max_len=40) or "ref"
        n = used.get(base, 0)
        if n == 0:
            tag = base
        else:
            if n <= len(ascii_lowercase):
                tag = f"{base}{ascii_lowercase[n - 1]}"
            else:
                tag = f"{base}_{n + 1}"
        used[base] = n + 1
        c["tag"] = tag


def _norm_text(value: str | None) -> str:
    return (value or "").strip().lower()


def _list_str(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value if v is not None]
    return []


def _limit_authors(authors: list[str] | None, max_authors: int) -> list[str] | None:
    if not isinstance(authors, list) or not authors:
        return None
    cleaned = [str(a) for a in authors if a is not None and str(a).strip()]
    if not cleaned:
        return None
    if max_authors == -1:
        return cleaned
    n = int(max_authors)
    if n <= 0:
        return ["et al."]
    if len(cleaned) <= n:
        return cleaned
    return cleaned[:n] + ["et al."]


def _truncate_text(text: str | None, max_chars: int) -> str | None:
    if not isinstance(text, str):
        return None
    t = text.strip()
    if not t:
        return None
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 1].rstrip() + "…"


def _strip_tags(text: str) -> str:
    cleaned = _re.sub(r"<[^>]+>", " ", text)
    cleaned = _html.unescape(cleaned)
    cleaned = _re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _decode_ddg_redirect(href: str) -> str:
    h = (href or "").strip()
    if not h:
        return h
    if h.startswith("//"):
        h = "https:" + h
    try:
        u = urlparse(h)
        if "duckduckgo.com" in (u.netloc or "") and u.path.startswith("/l/"):
            qs = parse_qs(u.query or "")
            uddg = qs.get("uddg", [None])[0]
            if isinstance(uddg, str) and uddg:
                return unquote(uddg)
    except Exception:
        return h
    return h


_LOW_VALUE_QUERY_TOKENS = {
    "biography",
    "bio",
    "wikipedia",
    "parasitologist",
    "profile",
    "about",
    "department",
    "university",
}


def _candidate_queries(q: str) -> list[str]:
    raw = (q or "").strip()
    if not raw:
        return []
    words = [w for w in raw.split() if w.strip()]
    cands: list[str] = []

    def _add(x: str) -> None:
        x = (x or "").strip()
        if x and x not in cands:
            cands.append(x)

    _add(raw)
    if len(words) > 2:
        _add(" ".join(words[:-1]))
    filtered = [w for w in words if w.lower() not in _LOW_VALUE_QUERY_TOKENS]
    if len(filtered) >= 2:
        _add(" ".join(filtered))
    if len(words) >= 2:
        _add(" ".join(words[:2]))
    return cands


def _looks_blocked(status_code: int, html: str) -> bool:
    if status_code == 202:
        return True
    h = (html or "").lower()
    if "challenge" in h and "result__a" not in h:
        return True
    if "unusual traffic" in h and "result__a" not in h:
        return True
    return False


def _norm_for_match(text: str | None) -> str:
    if not isinstance(text, str):
        return ""
    t = text.lower()
    t = _re.sub(r"\s+", " ", t).strip()
    return t


def _fallback_ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio() * 100.0


def _fuzzy_score(query: str, text: str) -> float:
    q = _norm_for_match(query)
    t = _norm_for_match(text)
    if not q or not t:
        return 0.0
    try:
        from rapidfuzz import fuzz  # type: ignore

        return float(fuzz.token_set_ratio(q, t))
    except Exception:
        return _fallback_ratio(q, t)


def _rerank_score(query: str, item: dict[str, Any]) -> tuple[float, dict[str, float]]:
    title = str(item.get("title") or "")
    abstract = str(item.get("abstract") or item.get("snippet") or "")
    journal = str(item.get("journalTitle") or item.get("journal") or "")
    title_s = _fuzzy_score(query, title)
    abs_s = _fuzzy_score(query, abstract)
    journal_s = _fuzzy_score(query, journal) if journal else 0.0
    score = 0.70 * title_s + 0.28 * abs_s + 0.02 * journal_s
    return score, {"title": title_s, "abstract": abs_s, "journal": journal_s}


def _passes_filters(
    *,
    title: str,
    authors: list[str] | None,
    year: int | None,
    doi: str | None,
    pmid: str | None,
    journal: str | None,
    year_from: int | None,
    year_to: int | None,
    author_includes: str | None,
    title_includes: str | None,
    journal_includes: str | None,
    doi_equals: str | None,
    pmid_equals: str | None,
    require_doi: bool,
) -> bool:
    if year_from is not None and (year is None or year < year_from):
        return False
    if year_to is not None and (year is None or year > year_to):
        return False

    if require_doi and not (isinstance(doi, str) and doi.strip()):
        return False

    if doi_equals is not None and _norm_text(doi) != _norm_text(doi_equals):
        return False
    if pmid_equals is not None and _norm_text(pmid) != _norm_text(pmid_equals):
        return False

    if title_includes is not None and _norm_text(title_includes) not in _norm_text(title):
        return False
    if journal_includes is not None and _norm_text(journal_includes) not in _norm_text(journal):
        return False
    if author_includes is not None:
        needle = _norm_text(author_includes)
        haystack = " ".join(_norm_text(a) for a in (authors or []))
        if needle not in haystack:
            return False

    return True


def _dedupe_key(item: dict[str, Any]) -> str:
    pmid = item.get("pmid")
    doi = item.get("doi")
    url = item.get("url")
    title = item.get("title")
    year = item.get("year")
    if isinstance(pmid, str) and pmid.strip():
        return f"pmid:{pmid.strip().lower()}"
    if isinstance(doi, str) and doi.strip():
        return f"doi:{doi.strip().lower()}"
    if isinstance(url, str) and url.strip():
        return f"url:{url.strip().lower()}"
    return f"title:{_norm_text(str(title))}|year:{year}"


class ResearchTools:
    """Web + literature search helpers used by planner agents."""

    def __init__(self, *, timeout_seconds: float = 15.0) -> None:
        self._timeout = timeout_seconds

    async def web_search(
        self,
        query: str,
        limit: int = 5,
        *,
        include_summary: bool = False,
        summary_max_chars: int = 600,
    ) -> dict[str, Any]:
        q = (query or "").strip()
        if not q:
            return {"results": [], "citations": [], "error": "query_required"}
        limit = max(1, min(int(limit or 5), 10))
        summary_max_chars = max(200, min(int(summary_max_chars or 600), 4000))

        results, effective_query, diag = await self._ddg_html_search(q, limit=limit)
        if include_summary and results:
            async with httpx.AsyncClient(
                timeout=min(self._timeout, 15.0),
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36"
                    ),
                    "Accept": (
                        "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                    ),
                    "Accept-Language": "en-US,en;q=0.9",
                },
            ) as client:
                summaries = await asyncio.gather(
                    *[
                        self._fetch_page_summary(
                            client, r.get("url"), max_chars=summary_max_chars
                        )
                        for r in results
                    ],
                    return_exceptions=True,
                )
            for r, s in zip(results, summaries, strict=False):
                summary = s.strip() if isinstance(s, str) and s.strip() else None
                r["summary"] = summary
                snip = r.get("snippet")
                if (not isinstance(snip, str)) or len(snip.strip()) < 40:
                    if summary:
                        r["snippet"] = summary

        citations: list[dict[str, Any]] = [
            Citation(
                id=_new_citation_id("web"),
                source="web",
                title=r.get("title") or (r.get("url") or "Web result"),
                url=r.get("url"),
                snippet=r.get("summary") or r.get("snippet"),
                accessed_at=_now_iso(),
            ).to_dict()
            for r in results
        ]
        _ensure_unique_citation_tags(citations)
        payload: dict[str, Any] = {
            "query": q,
            "effectiveQuery": effective_query,
            "searchAdjusted": effective_query != q,
            "searchDiagnostics": diag,
            "results": results,
            "citations": citations,
        }
        if not results and isinstance(diag, dict) and diag.get("blocked") is True:
            payload["error"] = "search_blocked"
        return payload

    async def _fetch_page_summary(
        self, client: httpx.AsyncClient, url: Any, *, max_chars: int
    ) -> str | None:
        if not isinstance(url, str) or not url.strip():
            return None
        u = url.strip()
        if u.lower().endswith(".pdf"):
            return None
        if "scholar.google." in u:
            return None

        try:
            resp = await client.get(
                u,
                follow_redirects=True,
                headers={"Referer": "https://duckduckgo.com/"},
            )
            resp.raise_for_status()
            html = resp.text or ""
        except Exception:
            return None

        meta_patterns = [
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+name=["\']twitter:description["\'][^>]+content=["\']([^"\']+)["\']',
        ]
        for pat in meta_patterns:
            m = _re.search(pat, html, flags=_re.IGNORECASE)
            if m:
                txt = _strip_tags(m.group(1))
                return _truncate_text(txt, max_chars) if txt else None

        paras = _re.findall(r"<p[^>]*>(.*?)</p>", html, flags=_re.IGNORECASE | _re.DOTALL)
        best: str | None = None
        for p in paras:
            txt = _strip_tags(p)
            low = txt.lower()
            if len(txt) < 60:
                continue
            if "toggle navigation" in low or "main navigation" in low:
                continue
            if best is None or len(txt) > len(best):
                best = txt
        return _truncate_text(best, max_chars) if best else None

    async def _ddg_html_search(
        self, q: str, *, limit: int
    ) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
        url = "https://html.duckduckgo.com/html/"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        def _parse_results(html: str) -> list[dict[str, Any]]:
            import re

            parsed: list[dict[str, Any]] = []
            # Find result links; snippets are nearby in the HTML.
            for m in re.finditer(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, flags=re.IGNORECASE):
                if len(parsed) >= limit:
                    break
                href = m.group(1)
                title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
                if not title:
                    continue
                window = html[m.end() : m.end() + 2000]
                m_snip = re.search(r'class="result__snippet"[^>]*>(.*?)</', window, flags=re.IGNORECASE)
                snippet_html = m_snip.group(1) if m_snip else ""
                snippet = re.sub(r"<[^>]+>", "", snippet_html).strip() or None
                parsed.append(
                    {"title": title, "url": _decode_ddg_redirect(href), "snippet": snippet}
                )
            return parsed

        diag: dict[str, Any] = {"blocked": False, "attempts": 0, "statusCodes": []}
        last_html = ""
        async with httpx.AsyncClient(timeout=self._timeout, headers=headers) as client:
            for cand in _candidate_queries(q):
                resp = await client.get(url, params={"q": cand}, follow_redirects=True)
                diag["attempts"] += 1
                diag["statusCodes"].append(resp.status_code)
                last_html = resp.text or ""
                if _looks_blocked(resp.status_code, last_html):
                    diag["blocked"] = True
                    continue
                results = _parse_results(last_html)
                if results:
                    return results, cand, diag

        if last_html and not diag.get("blocked"):
            return _parse_results(last_html), q, diag
        return [], q, diag

    async def literature_search(
        self,
        query: str,
        *,
        source: LiteratureSource = "all",
        limit: int = 5,
        sort: LiteratureSort = "relevance",
        include_abstract: bool = False,
        abstract_max_chars: int = 2000,
        max_authors: int = 2,
        year_from: int | None = None,
        year_to: int | None = None,
        author_includes: str | None = None,
        title_includes: str | None = None,
        journal_includes: str | None = None,
        doi_equals: str | None = None,
        pmid_equals: str | None = None,
        require_doi: bool = False,
    ) -> dict[str, Any]:
        q = (query or "").strip()
        if not q:
            return {"results": [], "citations": [], "error": "query_required"}
        limit = max(1, min(int(limit or 5), 25))
        abstract_max_chars = max(200, min(int(abstract_max_chars or 2000), 10000))
        if max_authors != -1:
            max_authors = max(0, min(int(max_authors or 2), 50))

        by_source: dict[str, dict[str, Any]] = {}

        async def _safe(name: str, coro):
            try:
                res = await coro
                return name, res if isinstance(res, dict) else {"error": "invalid_response"}
            except Exception as exc:
                return name, {
                    "query": q,
                    "source": name,
                    "results": [],
                    "citations": [],
                    "error": str(exc),
                }

        if source == "all":
            pairs = await asyncio.gather(
                _safe("europepmc", self._europe_pmc_search(q, limit=limit, abstract_max_chars=abstract_max_chars)),
                _safe("crossref", self._crossref_search(q, limit=limit, abstract_max_chars=abstract_max_chars)),
                _safe("openalex", self._openalex_search(q, limit=limit, abstract_max_chars=abstract_max_chars)),
                _safe("semanticscholar", self._semantic_scholar_search(q, limit=limit, abstract_max_chars=abstract_max_chars)),
                _safe("pubmed", self._pubmed_search(q, limit=limit, include_abstract=include_abstract, abstract_max_chars=abstract_max_chars)),
                _safe("arxiv", self._arxiv_search(q, limit=limit, abstract_max_chars=abstract_max_chars)),
                _safe("biorxiv", self._preprint_site_search(q, site="biorxiv.org", source="biorxiv", limit=limit, include_abstract=include_abstract, abstract_max_chars=abstract_max_chars)),
                _safe("medrxiv", self._preprint_site_search(q, site="medrxiv.org", source="medrxiv", limit=limit, include_abstract=include_abstract, abstract_max_chars=abstract_max_chars)),
            )
            by_source.update({k: v for k, v in pairs})
        else:
            # single-source
            if source == "europepmc":
                k, v = await _safe("europepmc", self._europe_pmc_search(q, limit=limit, abstract_max_chars=abstract_max_chars))
            elif source == "crossref":
                k, v = await _safe("crossref", self._crossref_search(q, limit=limit, abstract_max_chars=abstract_max_chars))
            elif source == "openalex":
                k, v = await _safe("openalex", self._openalex_search(q, limit=limit, abstract_max_chars=abstract_max_chars))
            elif source == "semanticscholar":
                k, v = await _safe("semanticscholar", self._semantic_scholar_search(q, limit=limit, abstract_max_chars=abstract_max_chars))
            elif source == "pubmed":
                k, v = await _safe("pubmed", self._pubmed_search(q, limit=limit, include_abstract=include_abstract, abstract_max_chars=abstract_max_chars))
            elif source == "arxiv":
                k, v = await _safe("arxiv", self._arxiv_search(q, limit=limit, abstract_max_chars=abstract_max_chars))
            elif source == "biorxiv":
                k, v = await _safe("biorxiv", self._preprint_site_search(q, site="biorxiv.org", source="biorxiv", limit=limit, include_abstract=include_abstract, abstract_max_chars=abstract_max_chars))
            else:  # medrxiv
                k, v = await _safe("medrxiv", self._preprint_site_search(q, site="medrxiv.org", source="medrxiv", limit=limit, include_abstract=include_abstract, abstract_max_chars=abstract_max_chars))
            by_source[k] = v

        # Merge + filter + dedupe; keep citations aligned via dedupe key.
        filtered: list[dict[str, Any]] = []
        citations_by_key: dict[str, dict[str, Any]] = {}
        seen: set[str] = set()

        for src, payload in by_source.items():
            results = payload.get("results") if isinstance(payload, dict) else None
            citations = payload.get("citations") if isinstance(payload, dict) else None
            if not isinstance(results, list) or not isinstance(citations, list):
                continue
            for i, item in enumerate(results):
                if not isinstance(item, dict):
                    continue
                c = citations[i] if i < len(citations) else None
                title = str(item.get("title") or "").strip()
                authors = item.get("authors") if isinstance(item.get("authors"), list) else None
                year = item.get("year") if isinstance(item.get("year"), int) else None
                doi = item.get("doi") if isinstance(item.get("doi"), str) else None
                pmid = item.get("pmid") if isinstance(item.get("pmid"), str) else None
                journal = item.get("journalTitle") or item.get("journal")
                journal = str(journal).strip() if journal is not None else None

                if not _passes_filters(
                    title=title,
                    authors=_list_str(authors) if authors is not None else None,
                    year=year,
                    doi=doi,
                    pmid=pmid,
                    journal=journal,
                    year_from=year_from,
                    year_to=year_to,
                    author_includes=author_includes,
                    title_includes=title_includes,
                    journal_includes=journal_includes,
                    doi_equals=doi_equals,
                    pmid_equals=pmid_equals,
                    require_doi=require_doi,
                ):
                    continue

                key = _dedupe_key(item)
                if key in seen:
                    continue
                seen.add(key)
                filtered.append(
                    {
                        **item,
                        "source": src,
                        "authors": _limit_authors(_list_str(authors) if authors else None, max_authors),
                        "abstract": _truncate_text(item.get("abstract"), abstract_max_chars)
                        if include_abstract
                        else item.get("abstract"),
                    }
                )

                if isinstance(c, dict):
                    c2 = {**c}
                    if "authors" in c2:
                        c2["authors"] = _limit_authors(_list_str(c2.get("authors")), max_authors)
                    citations_by_key[key] = c2

        if sort == "newest":
            filtered.sort(
                key=lambda r: (r.get("year") is not None, r.get("year") or 0),
                reverse=True,
            )

        def _ordered_citations(results_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
            ordered: list[dict[str, Any]] = []
            for r in results_list:
                key = _dedupe_key(r)
                c = citations_by_key.get(key)
                if c is not None:
                    ordered.append(c)
            return ordered

        payload: dict[str, Any] = {
            "query": q,
            "source": source,
            "sort": sort,
            "includeAbstract": include_abstract,
            "abstractMaxChars": abstract_max_chars,
            "maxAuthors": max_authors,
            "filters": {
                "yearFrom": year_from,
                "yearTo": year_to,
                "authorIncludes": author_includes,
                "titleIncludes": title_includes,
                "journalIncludes": journal_includes,
                "doiEquals": doi_equals,
                "pmidEquals": pmid_equals,
                "requireDoi": require_doi,
            },
            "results": filtered[:limit],
            "citations": _ordered_citations(filtered),
        }

        if sort == "relevance" and source == "all" and filtered:
            scored: list[dict[str, Any]] = []
            for item in filtered:
                if not isinstance(item, dict):
                    continue
                score, parts = _rerank_score(q, item)
                scored.append({**item, "score": round(score, 2), "scoreParts": parts})
            scored.sort(key=lambda r: (r.get("score") is not None, r.get("score") or 0.0), reverse=True)
            filtered = scored
            payload["results"] = filtered[:limit]
            payload["citations"] = _ordered_citations(filtered)

        if source == "all":
            payload["bySource"] = by_source
        if isinstance(payload.get("citations"), list):
            _ensure_unique_citation_tags(payload["citations"])
        return payload

    async def _europe_pmc_search(
        self, query: str, *, limit: int, abstract_max_chars: int
    ) -> dict[str, Any]:
        url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        params = {
            "query": query,
            "format": "json",
            "pageSize": str(limit),
            "resultType": "core",
        }
        headers = {"User-Agent": "pathfinder-planner/1.0 (+https://pathfinder.veupathdb.org)"}
        async with httpx.AsyncClient(timeout=self._timeout, headers=headers) as client:
            resp = await client.get(url, params=params, follow_redirects=True)
            resp.raise_for_status()
            payload = resp.json()

        hits = payload.get("resultList", {}).get("result", []) if isinstance(payload, dict) else []
        results: list[dict[str, Any]] = []
        citations: list[dict[str, Any]] = []
        for item in hits:
            if not isinstance(item, dict):
                continue
            title = (item.get("title") or "").strip()
            year_i: int | None
            try:
                year_i = int(item.get("pubYear")) if item.get("pubYear") is not None else None
            except Exception:
                year_i = None
            doi = item.get("doi") if isinstance(item.get("doi"), str) else None
            pmid = item.get("pmid") if isinstance(item.get("pmid"), str) else None
            author_str = item.get("authorString")
            authors = (
                [a.strip() for a in author_str.split(",") if a.strip()]
                if isinstance(author_str, str)
                else None
            )
            journal = item.get("journalTitle")
            journal = journal.strip() if isinstance(journal, str) else None

            link = None
            if doi:
                link = f"https://doi.org/{doi}"
            elif pmid:
                link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

            abstract = item.get("abstractText")
            abstract = _truncate_text(abstract if isinstance(abstract, str) else None, abstract_max_chars)
            results.append(
                {
                    "title": title,
                    "year": year_i,
                    "doi": doi,
                    "pmid": pmid,
                    "url": link,
                    "authors": authors,
                    "journalTitle": journal,
                    "abstract": abstract,
                    "snippet": journal,
                }
            )
            citations.append(
                Citation(
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
            )
        _ensure_unique_citation_tags(citations)
        return {"query": query, "source": "europepmc", "results": results, "citations": citations}

    async def _crossref_search(
        self, query: str, *, limit: int, abstract_max_chars: int
    ) -> dict[str, Any]:
        url = "https://api.crossref.org/works"
        params = {"query": query, "rows": str(limit)}
        headers = {"User-Agent": "pathfinder-planner/1.0 (mailto:unknown@example.com)"}
        async with httpx.AsyncClient(timeout=self._timeout, headers=headers) as client:
            resp = await client.get(url, params=params, follow_redirects=True)
            resp.raise_for_status()
            payload = resp.json()

        items = payload.get("message", {}).get("items", []) if isinstance(payload, dict) else []
        results: list[dict[str, Any]] = []
        citations: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            title_list = item.get("title")
            title = title_list[0].strip() if isinstance(title_list, list) and title_list else ""
            doi = item.get("DOI") if isinstance(item.get("DOI"), str) else None
            url_item = item.get("URL") if isinstance(item.get("URL"), str) else None
            year_i: int | None = None
            published = item.get("published-print") or item.get("published-online") or {}
            parts = published.get("date-parts") if isinstance(published, dict) else None
            if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0]:
                try:
                    year_i = int(parts[0][0])
                except Exception:
                    year_i = None
            authors = None
            raw_authors = item.get("author")
            if isinstance(raw_authors, list):
                authors = []
                for a in raw_authors:
                    if not isinstance(a, dict):
                        continue
                    family = a.get("family")
                    given = a.get("given")
                    if family and given:
                        authors.append(f"{given} {family}")
                    elif family:
                        authors.append(str(family))
            journal = None
            ct = item.get("container-title")
            if isinstance(ct, list) and ct:
                journal = str(ct[0]).strip()

            results.append(
                {
                    "title": title,
                    "year": year_i,
                    "doi": doi,
                    "url": url_item or (f"https://doi.org/{doi}" if doi else None),
                    "authors": authors,
                    "journalTitle": journal,
                    "snippet": journal,
                }
            )
            citations.append(
                Citation(
                    id=_new_citation_id("crossref"),
                    source="crossref",
                    title=title or (url_item or "Crossref result"),
                    url=url_item or (f"https://doi.org/{doi}" if doi else None),
                    authors=authors,
                    year=year_i,
                    doi=doi,
                    snippet=journal,
                    accessed_at=_now_iso(),
                ).to_dict()
            )
        _ensure_unique_citation_tags(citations)
        return {"query": query, "source": "crossref", "results": results, "citations": citations}

    async def _openalex_search(
        self, query: str, *, limit: int, abstract_max_chars: int
    ) -> dict[str, Any]:
        url = "https://api.openalex.org/works"
        params = {"search": query, "per-page": str(limit)}
        headers = {"User-Agent": "pathfinder-planner/1.0 (+https://pathfinder.veupathdb.org)"}
        async with httpx.AsyncClient(timeout=self._timeout, headers=headers) as client:
            resp = await client.get(url, params=params, follow_redirects=True)
            resp.raise_for_status()
            payload = resp.json()

        items = payload.get("results", []) if isinstance(payload, dict) else []
        results: list[dict[str, Any]] = []
        citations: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            year_i = item.get("publication_year")
            year = int(year_i) if isinstance(year_i, int) else None
            doi = item.get("doi")
            doi = str(doi).replace("https://doi.org/", "") if isinstance(doi, str) else None
            url_item = item.get("id") if isinstance(item.get("id"), str) else None
            journal = None
            hv = item.get("host_venue")
            if isinstance(hv, dict):
                journal = hv.get("display_name")
            journal = str(journal).strip() if journal else None
            authors: list[str] | None = None
            auths = item.get("authorships")
            if isinstance(auths, list):
                authors = []
                for a in auths:
                    if not isinstance(a, dict):
                        continue
                    au = a.get("author")
                    if isinstance(au, dict) and au.get("display_name"):
                        authors.append(str(au.get("display_name")))

            abstract = None
            inv = item.get("abstract_inverted_index")
            if isinstance(inv, dict):
                # Best-effort reconstruction.
                pairs: list[tuple[int, str]] = []
                for word, idxs in inv.items():
                    if not isinstance(word, str) or not isinstance(idxs, list):
                        continue
                    for i in idxs:
                        if isinstance(i, int):
                            pairs.append((i, word))
                if pairs:
                    pairs.sort(key=lambda x: x[0])
                    abstract = " ".join(w for _, w in pairs)
            abstract = _truncate_text(abstract, abstract_max_chars)

            results.append(
                {
                    "title": title,
                    "year": year,
                    "doi": doi,
                    "url": f"https://doi.org/{doi}" if doi else url_item,
                    "authors": authors,
                    "journalTitle": journal,
                    "abstract": abstract,
                    "snippet": abstract or journal,
                }
            )
            citations.append(
                Citation(
                    id=_new_citation_id("openalex"),
                    source="openalex",
                    title=title or (url_item or "OpenAlex result"),
                    url=f"https://doi.org/{doi}" if doi else url_item,
                    authors=authors,
                    year=year,
                    doi=doi,
                    snippet=abstract or journal,
                    accessed_at=_now_iso(),
                ).to_dict()
            )
        _ensure_unique_citation_tags(citations)
        return {"query": query, "source": "openalex", "results": results, "citations": citations}

    async def _semantic_scholar_search(
        self, query: str, *, limit: int, abstract_max_chars: int
    ) -> dict[str, Any]:
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            "query": query,
            "limit": str(limit),
            "fields": "title,year,authors,url,abstract,journal,externalIds",
        }
        headers = {"User-Agent": "pathfinder-planner/1.0 (+https://pathfinder.veupathdb.org)"}
        async with httpx.AsyncClient(timeout=self._timeout, headers=headers) as client:
            resp = await client.get(url, params=params, follow_redirects=True)
            resp.raise_for_status()
            payload = resp.json()

        items = payload.get("data", []) if isinstance(payload, dict) else []
        results: list[dict[str, Any]] = []
        citations: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            year = item.get("year") if isinstance(item.get("year"), int) else None
            url_item = item.get("url") if isinstance(item.get("url"), str) else None
            authors = None
            raw_authors = item.get("authors")
            if isinstance(raw_authors, list):
                authors = [str(a.get("name")) for a in raw_authors if isinstance(a, dict) and a.get("name")]
            abstract = item.get("abstract") if isinstance(item.get("abstract"), str) else None
            abstract = _truncate_text(abstract, abstract_max_chars)
            journal = None
            j = item.get("journal")
            if isinstance(j, dict) and j.get("name"):
                journal = str(j.get("name"))
            ext = item.get("externalIds")
            doi = None
            pmid = None
            if isinstance(ext, dict):
                if isinstance(ext.get("DOI"), str):
                    doi = ext.get("DOI")
                if isinstance(ext.get("PubMed"), str):
                    pmid = ext.get("PubMed")

            results.append(
                {
                    "title": title,
                    "year": year,
                    "doi": doi,
                    "pmid": pmid,
                    "url": url_item or (f"https://doi.org/{doi}" if doi else None),
                    "authors": authors,
                    "journalTitle": journal,
                    "abstract": abstract,
                    "snippet": abstract or journal,
                }
            )
            citations.append(
                Citation(
                    id=_new_citation_id("s2"),
                    source="semanticscholar",
                    title=title or (url_item or "Semantic Scholar result"),
                    url=url_item or (f"https://doi.org/{doi}" if doi else None),
                    authors=authors,
                    year=year,
                    doi=doi,
                    pmid=pmid,
                    snippet=abstract or journal,
                    accessed_at=_now_iso(),
                ).to_dict()
            )
        _ensure_unique_citation_tags(citations)
        return {
            "query": query,
            "source": "semanticscholar",
            "results": results,
            "citations": citations,
        }

    async def _pubmed_search(
        self,
        query: str,
        *,
        limit: int,
        include_abstract: bool,
        abstract_max_chars: int,
    ) -> dict[str, Any]:
        headers = {"User-Agent": "pathfinder-planner/1.0 (+https://pathfinder.veupathdb.org)"}
        async with httpx.AsyncClient(timeout=self._timeout, headers=headers) as client:
            esearch = await client.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                params={"db": "pubmed", "term": query, "retmax": str(limit), "retmode": "json"},
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
                return {"query": query, "source": "pubmed", "results": [], "citations": []}

            esummary = await client.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
                params={"db": "pubmed", "id": ",".join(pmids), "retmode": "json"},
            )
            esummary.raise_for_status()
            sum_payload = esummary.json()
            sum_result = sum_payload.get("result") if isinstance(sum_payload, dict) else {}

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
                        abstracts_by_pmid[pmid] = _strip_tags(m.group(1))

        results: list[dict[str, Any]] = []
        citations: list[dict[str, Any]] = []
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
                authors = [str(a.get("name")) for a in raw_authors if isinstance(a, dict) and a.get("name")]
            journal = meta.get("fulljournalname")
            journal = str(journal).strip() if journal else None
            abstract = abstracts_by_pmid.get(pmid)
            abstract = _truncate_text(abstract, abstract_max_chars) if include_abstract else None

            url_item = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            results.append(
                {
                    "title": title,
                    "year": year,
                    "pmid": pmid,
                    "url": url_item,
                    "authors": authors,
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
        _ensure_unique_citation_tags(citations)
        return {"query": query, "source": "pubmed", "results": results, "citations": citations}

    async def _arxiv_search(
        self, query: str, *, limit: int, abstract_max_chars: int
    ) -> dict[str, Any]:
        url = "http://export.arxiv.org/api/query"
        params = {"search_query": f"all:{query}", "start": "0", "max_results": str(limit)}
        headers = {"User-Agent": "pathfinder-planner/1.0 (+https://pathfinder.veupathdb.org)"}
        async with httpx.AsyncClient(timeout=self._timeout, headers=headers) as client:
            resp = await client.get(url, params=params, follow_redirects=True)
            resp.raise_for_status()
            xml = resp.text or ""

        # Minimal parser: handle empty feeds gracefully (unit tests use empty feed).
        entries = _re.findall(r"<entry>(.*?)</entry>", xml, flags=_re.IGNORECASE | _re.DOTALL)
        results: list[dict[str, Any]] = []
        citations: list[dict[str, Any]] = []
        for e in entries[:limit]:
            title = _strip_tags("".join(_re.findall(r"<title>(.*?)</title>", e, flags=_re.IGNORECASE | _re.DOTALL))).strip()
            link_m = _re.search(r'<link[^>]+href="([^"]+)"', e, flags=_re.IGNORECASE)
            url_item = link_m.group(1) if link_m else None
            abstract = _strip_tags("".join(_re.findall(r"<summary>(.*?)</summary>", e, flags=_re.IGNORECASE | _re.DOTALL))).strip()
            abstract = _truncate_text(abstract, abstract_max_chars)
            results.append({"title": title, "url": url_item, "abstract": abstract, "snippet": abstract})
            citations.append(
                Citation(
                    id=_new_citation_id("arxiv"),
                    source="arxiv",
                    title=title or (url_item or "arXiv result"),
                    url=url_item,
                    snippet=abstract,
                    accessed_at=_now_iso(),
                ).to_dict()
            )
        _ensure_unique_citation_tags(citations)
        return {"query": query, "source": "arxiv", "results": results, "citations": citations}

    async def _preprint_site_search(
        self,
        query: str,
        *,
        site: str,
        source: Literal["biorxiv", "medrxiv"],
        limit: int,
        include_abstract: bool,
        abstract_max_chars: int,
    ) -> dict[str, Any]:
        # Use DDG HTML endpoint (tests mock duckduckgo.com/html/ for preprints).
        ddg_url = "https://duckduckgo.com/html/"
        params = {"q": f"site:{site} {query}"}
        headers = {"User-Agent": "pathfinder-planner/1.0 (+https://pathfinder.veupathdb.org)"}
        async with httpx.AsyncClient(timeout=self._timeout, headers=headers) as client:
            resp = await client.get(ddg_url, params=params, follow_redirects=True)
            resp.raise_for_status()
            html = resp.text or ""

        # Reuse the simple result parser shape.
        results: list[dict[str, Any]] = []
        citations: list[dict[str, Any]] = []
        for m in _re.finditer(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, flags=_re.IGNORECASE):
            if len(results) >= limit:
                break
            href = m.group(1)
            title = _strip_tags(m.group(2))
            url_item = _decode_ddg_redirect(href)
            results.append({"title": title, "url": url_item, "snippet": None})
            citations.append(
                Citation(
                    id=_new_citation_id(source),
                    source=source,
                    title=title or (url_item or f"{source} result"),
                    url=url_item,
                    snippet=None,
                    accessed_at=_now_iso(),
                ).to_dict()
            )

        # Optional: fetch a summary if requested (best-effort).
        if include_abstract and results:
            async with httpx.AsyncClient(
                timeout=min(self._timeout, 15.0),
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36"
                    ),
                    "Accept-Language": "en-US,en;q=0.9",
                },
            ) as client:
                summaries = await asyncio.gather(
                    *[self._fetch_page_summary(client, r.get("url"), max_chars=abstract_max_chars) for r in results],
                    return_exceptions=True,
                )
            for r, s in zip(results, summaries, strict=False):
                if isinstance(s, str) and s.strip():
                    r["abstract"] = s.strip()
                    r["snippet"] = s.strip()

        _ensure_unique_citation_tags(citations)
        return {"query": query, "source": source, "results": results, "citations": citations}


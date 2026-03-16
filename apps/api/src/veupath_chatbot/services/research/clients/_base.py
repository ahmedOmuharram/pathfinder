"""Shared base for literature search API clients."""

from typing import cast

from veupath_chatbot.domain.research.citations import (
    Citation,
    CitationSource,
    _new_citation_id,
    _now_iso,
    ensure_unique_citation_tags,
)
from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue

API_USER_AGENT = "pathfinder-planner/1.0"


class BaseClient:
    """Common initialisation for all literature API clients."""

    def __init__(self, *, timeout_seconds: float = 15.0) -> None:
        self._timeout = timeout_seconds

    # -- Template helpers --------------------------------------------------

    def _build_results(
        self,
        raw_items: list[JSONValue],
        *,
        abstract_max_chars: int,
    ) -> tuple[JSONArray, list[JSONObject]]:
        """Iterate *raw_items*, calling ``_parse_item`` on each.

        Returns a ``(results, citations)`` pair ready for
        :func:`build_response`.
        """
        results: JSONArray = []
        citations: list[JSONObject] = []
        for raw in raw_items:
            pair = self._parse_item(raw, abstract_max_chars=abstract_max_chars)
            if pair is None:
                continue
            result, citation = pair
            results.append(result)
            citations.append(citation)
        return results, citations

    def _parse_item(
        self,
        raw: JSONValue,
        *,
        abstract_max_chars: int,
    ) -> tuple[JSONObject, JSONObject] | None:
        """Parse one raw API item into ``(result_dict, citation_dict)``.

        Return ``None`` to skip the item.  Subclasses **must** override.
        """
        raise NotImplementedError


class StandardClient(BaseClient):
    """Client with the standard fetch-parse-build search pattern.

    Subclasses implement ``_source_name``, ``_fetch_raw``, and
    ``_parse_item``.  The ``search`` method is inherited.
    """

    _source_name: str = ""  # override in subclass

    async def search(
        self, query: str, *, limit: int, abstract_max_chars: int
    ) -> JSONObject:
        raw_items = await self._fetch_raw(query, limit=limit)
        results, citations = self._build_results(
            raw_items, abstract_max_chars=abstract_max_chars
        )
        return build_response(
            query=query,
            source=self._source_name,
            results=results,
            citations=citations,
        )

    async def _fetch_raw(self, query: str, *, limit: int) -> list[JSONValue]:
        raise NotImplementedError


def make_citation(
    *,
    source: CitationSource,
    id_prefix: str,
    title: str,
    url: str | None = None,
    authors: list[str] | None = None,
    year: int | None = None,
    doi: str | None = None,
    pmid: str | None = None,
    snippet: str | None = None,
) -> JSONObject:
    """Build a citation dict from common fields."""
    return Citation(
        id=_new_citation_id(id_prefix),
        source=source,
        title=title,
        url=url,
        authors=authors,
        year=year,
        doi=doi,
        pmid=pmid,
        snippet=snippet,
        accessed_at=_now_iso(),
    ).to_dict()


def build_response(
    *,
    query: str,
    source: str,
    results: JSONArray,
    citations: list[JSONObject],
) -> JSONObject:
    """Build the standard client response dict, deduplicating citation tags."""
    ensure_unique_citation_tags(citations)
    return {
        "query": query,
        "source": source,
        "results": results,
        "citations": cast(JSONValue, citations),
    }

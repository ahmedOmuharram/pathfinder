"""Shared base for literature search API clients."""

import asyncio
from typing import cast

from veupath_chatbot.domain.research.citations import (
    ensure_unique_citation_tags,
)
from veupath_chatbot.platform.errors import ExternalServiceError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue

logger = get_logger(__name__)

API_USER_AGENT = "pathfinder-planner/1.0"

_DEFAULT_MAX_RETRIES = 3
_DEFAULT_BACKOFF_BASE_S = 1.0


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

    Rate-limit handling (HTTP 429) with exponential backoff is built in.
    Subclasses can override ``_max_retries`` and ``_backoff_base_s``.
    """

    _source_name: str = ""  # override in subclass
    _max_retries: int = _DEFAULT_MAX_RETRIES
    _backoff_base_s: float = _DEFAULT_BACKOFF_BASE_S

    async def search(
        self, query: str, *, limit: int, abstract_max_chars: int
    ) -> JSONObject:
        raw_items = await self._fetch_with_retry(query, limit=limit)
        results, citations = self._build_results(
            raw_items, abstract_max_chars=abstract_max_chars
        )
        return build_response(
            query=query,
            source=self._source_name,
            results=results,
            citations=citations,
        )

    async def _fetch_with_retry(
        self, query: str, *, limit: int
    ) -> list[JSONValue]:
        """Call ``_fetch_raw`` with retry on 429 and transient errors."""
        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                return await self._fetch_raw(query, limit=limit)
            except ExternalServiceError as exc:
                last_exc = exc
                if "429" in str(exc):
                    wait = self._backoff_base_s * (2 ** attempt)
                    logger.warning(
                        "%s 429, retrying",
                        self._source_name,
                        attempt=attempt + 1,
                        wait_s=wait,
                    )
                    await asyncio.sleep(wait)
                    continue
                raise
            except Exception as exc:
                last_exc = exc
                if attempt < self._max_retries - 1:
                    wait = self._backoff_base_s * (2 ** attempt)
                    logger.warning(
                        "%s request failed, retrying",
                        self._source_name,
                        attempt=attempt + 1,
                        wait_s=wait,
                        error=str(exc),
                    )
                    await asyncio.sleep(wait)
                    continue
                raise
        raise ExternalServiceError(self._source_name, str(last_exc))

    async def _fetch_raw(self, query: str, *, limit: int) -> list[JSONValue]:
        raise NotImplementedError


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
        "citations": cast("JSONValue", citations),
    }

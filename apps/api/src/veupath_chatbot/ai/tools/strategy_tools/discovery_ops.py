"""Discovery/search helper tools (AI-exposed)."""

import re
from typing import Annotated

import httpx
from kani import AIParam, ai_function

from veupath_chatbot.domain.strategy.explain import explain_operation
from veupath_chatbot.domain.strategy.ops import parse_op
from veupath_chatbot.platform.errors import ErrorCode
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.platform.types import (
    JSONArray,
    JSONObject,
    JSONValue,
    as_json_object,
)
from veupath_chatbot.services.catalog.searches import (
    get_raw_record_types,
    get_raw_searches,
)
from veupath_chatbot.services.strategies.engine.helpers import StrategyToolsHelpers

logger = get_logger(__name__)


def _extract_terms(keywords: list[str] | str) -> list[str]:
    """Extract and lowercase search terms from keywords input."""
    if isinstance(keywords, str):
        raw_terms = re.findall(r"[A-Za-z0-9]+", keywords)
    else:
        raw_terms_list: list[str] = []
        for item in keywords:
            raw_terms_list.extend(re.findall(r"[A-Za-z0-9]+", str(item)))
        raw_terms = raw_terms_list
    return [t.lower() for t in raw_terms if t]


async def _resolve_record_types(
    session_site_id: str,
    resolved_record_type: str | None,
) -> list[str]:
    """Resolve the list of record types to search."""
    if resolved_record_type:
        return [resolved_record_type]
    record_types_list: list[str] = []
    record_types_raw = await get_raw_record_types(session_site_id)
    for rt_value in record_types_raw:
        if not isinstance(rt_value, dict):
            continue
        rt = as_json_object(rt_value)
        url_segment = rt.get("urlSegment")
        name_value = rt.get("name")
        if isinstance(url_segment, str):
            record_types_list.append(url_segment)
        elif isinstance(name_value, str):
            record_types_list.append(name_value)
    return record_types_list


def _extract_search_info(search: JSONObject) -> tuple[str, str, str, str]:
    """Extract name, display, short, and description from a search dict."""
    url_segment_value = search.get("urlSegment")
    name_value = search.get("name")
    display_value = search.get("displayName")
    short_value = search.get("shortDisplayName")
    description_value = search.get("description")
    name = (
        str(url_segment_value)
        if isinstance(url_segment_value, str)
        else (str(name_value) if isinstance(name_value, str) else "")
    )
    display = str(display_value) if isinstance(display_value, str) else ""
    short = str(short_value) if isinstance(short_value, str) else ""
    description = str(description_value) if isinstance(description_value, str) else ""
    return name, display, short, description


def _score_search(
    terms: list[str],
    name: str,
    display: str,
    short: str,
    description: str,
) -> int:
    """Score a search against terms."""
    haystack = " ".join([name, display, short, description]).lower()
    return sum(1 for term in terms if term in haystack)


def _sort_key(item_value: JSONValue) -> tuple[int, str]:
    """Sort key for search results: by score descending, then display name."""
    if not isinstance(item_value, dict):
        return (0, "")
    item = as_json_object(item_value)
    score_value = item.get("score")
    display_name_value = item.get("displayName")
    score = int(score_value) if isinstance(score_value, (int, float)) else 0
    display_name = (
        str(display_name_value) if isinstance(display_name_value, str) else ""
    )
    return (-score, display_name)


class StrategyDiscoveryOps(StrategyToolsHelpers):
    """Discovery/search tools."""

    @ai_function()
    async def search_searches_by_keywords(
        self,
        keywords: Annotated[
            list[str] | str,
            AIParam(desc="Keywords to match (e.g., ['otto', '2014', 'gametocyte'])"),
        ],
        record_type: Annotated[
            str | None, AIParam(desc="Optional record type to restrict the search")
        ] = None,
        limit: Annotated[int, AIParam(desc="Max number of results")] = 20,
    ) -> JSONObject:
        """Search available questions by keywords across name/display/description."""
        terms = _extract_terms(keywords)
        if not terms:
            return tool_error(
                ErrorCode.VALIDATION_ERROR, "No keywords provided", keywords=[]
            )

        resolved_record_type = (
            await self._resolve_record_type(record_type) if record_type else None
        )
        record_types = await _resolve_record_types(
            self.session.site_id, resolved_record_type
        )

        matches = await self._collect_matches(record_types, terms)
        matches.sort(key=_sort_key)
        return {"keywords": terms, "results": matches[: max(limit, 1)]}

    async def _collect_matches(
        self,
        record_types: list[str],
        terms: list[str],
    ) -> JSONArray:
        """Collect matching searches across all record types."""
        matches: JSONArray = []
        for rt_name in record_types:
            try:
                searches = await get_raw_searches(self.session.site_id, rt_name)
            except httpx.HTTPError, KeyError:
                logger.warning(
                    "Failed to fetch searches for record type %s",
                    rt_name,
                    exc_info=True,
                )
                continue
            self._match_searches(searches, rt_name, terms, matches)
        return matches

    def _match_searches(
        self,
        searches: list[object],
        rt_name: str,
        terms: list[str],
        matches: JSONArray,
    ) -> None:
        """Match individual searches and append to matches."""
        for search_value in searches:
            if not isinstance(search_value, dict):
                continue
            search = as_json_object(search_value)
            name, display, short, description = _extract_search_info(search)
            score = _score_search(terms, name, display, short, description)
            if score == 0:
                continue
            haystack = " ".join([name, display, short, description]).lower()
            matches.append(
                {
                    "recordType": rt_name,
                    "searchName": name or display,
                    "displayName": display or name,
                    "description": description,
                    "score": score,
                    "matchedKeywords": [t for t in terms if t in haystack],
                }
            )

    @ai_function()
    async def explain_operator(
        self,
        operator: Annotated[
            str,
            AIParam(desc="Operator to explain (INTERSECT, UNION, etc.)"),
        ],
    ) -> str:
        """Explain what a combine operator does."""
        op = parse_op(operator)
        return explain_operation(op)

"""Discovery/search helper tools (AI-exposed)."""

from __future__ import annotations

import re
from typing import Annotated

from kani import AIParam, ai_function

from veupath_chatbot.domain.strategy.explain import explain_operation
from veupath_chatbot.domain.strategy.ops import parse_op
from veupath_chatbot.integrations.veupathdb.discovery import get_discovery_service
from veupath_chatbot.platform.errors import ErrorCode
from veupath_chatbot.platform.types import (
    JSONArray,
    JSONObject,
    JSONValue,
)
from veupath_chatbot.services.strategies.engine.helpers import StrategyToolsHelpers


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
        if isinstance(keywords, str):
            raw_terms = re.findall(r"[A-Za-z0-9]+", keywords)
        else:
            raw_terms_list: list[str] = []
            for item in keywords:
                raw_terms_list.extend(re.findall(r"[A-Za-z0-9]+", str(item)))
            raw_terms = raw_terms_list
        terms = [t.lower() for t in raw_terms if t]
        if not terms:
            return self._tool_error(
                ErrorCode.VALIDATION_ERROR, "No keywords provided", keywords=[]
            )

        discovery = get_discovery_service()
        matches: JSONArray = []

        record_types: list[str] = []
        resolved_record_type = (
            await self._resolve_record_type(record_type) if record_type else None
        )
        if resolved_record_type:
            record_types = [resolved_record_type]
        else:
            from veupath_chatbot.platform.types import as_json_object

            record_types_list: list[str] = []
            record_types_raw = await discovery.get_record_types(self.session.site_id)
            for rt_value in record_types_raw:
                if not isinstance(rt_value, dict):
                    continue
                rt = as_json_object(rt_value)
                url_segment = rt.get("urlSegment")
                name_value = rt.get("name")
                rt_name: str | None = None
                if isinstance(url_segment, str):
                    rt_name = url_segment
                elif isinstance(name_value, str):
                    rt_name = name_value
                if rt_name:
                    record_types_list.append(rt_name)
            record_types = record_types_list

        for rt_name in record_types:
            try:
                searches = await discovery.get_searches(self.session.site_id, rt_name)
            except Exception:
                continue
            from veupath_chatbot.platform.types import as_json_object

            for search_value in searches:
                if not isinstance(search_value, dict):
                    continue
                search = as_json_object(search_value)
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
                description = (
                    str(description_value) if isinstance(description_value, str) else ""
                )
                haystack = " ".join([name, display, short, description]).lower()
                score = sum(1 for term in terms if term in haystack)
                if score == 0:
                    continue
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

        def sort_key(item_value: JSONValue) -> tuple[int, str]:
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

        matches.sort(key=sort_key)
        return {"keywords": terms, "results": matches[: max(limit, 1)]}

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

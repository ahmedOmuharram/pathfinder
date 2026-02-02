"""Discovery/search helper tools (AI-exposed)."""

from __future__ import annotations

import re
from typing import Annotated, Any

from kani import AIParam, ai_function

from veupath_chatbot.platform.errors import ErrorCode
from veupath_chatbot.domain.strategy.explain import explain_operation
from veupath_chatbot.domain.strategy.ops import parse_op
from veupath_chatbot.integrations.veupathdb.discovery import get_discovery_service


class StrategyDiscoveryOps:
    """Discovery/search tools."""

    @ai_function()
    async def search_searches_by_keywords(
        self,
        keywords: Annotated[
            list[str] | str,
            AIParam(
                desc="Keywords to match (e.g., ['otto', '2014', 'gametocyte'])"
            ),
        ],
        record_type: Annotated[
            str | None, AIParam(desc="Optional record type to restrict the search")
        ] = None,
        limit: Annotated[int, AIParam(desc="Max number of results")] = 20,
    ) -> dict[str, Any]:
        """Search available questions by keywords across name/display/description."""
        if isinstance(keywords, str):
            raw_terms = re.findall(r"[A-Za-z0-9]+", keywords)
        else:
            raw_terms: list[str] = []
            for item in keywords:
                raw_terms.extend(re.findall(r"[A-Za-z0-9]+", str(item)))
        terms = [t.lower() for t in raw_terms if t]
        if not terms:
            return self._tool_error(
                ErrorCode.VALIDATION_ERROR, "No keywords provided", keywords=[]
            )

        discovery = get_discovery_service()
        matches: list[dict[str, Any]] = []

        record_types: list[str] = []
        resolved_record_type = (
            await self._resolve_record_type(record_type) if record_type else None
        )
        if resolved_record_type:
            record_types = [resolved_record_type]
        else:
            record_types = [
                rt.get("urlSegment", rt.get("name", ""))
                for rt in await discovery.get_record_types(self.session.site_id)
                if rt.get("urlSegment") or rt.get("name")
            ]

        for rt_name in record_types:
            try:
                searches = await discovery.get_searches(self.session.site_id, rt_name)
            except Exception:
                continue
            for search in searches:
                name = search.get("urlSegment") or search.get("name") or ""
                display = search.get("displayName") or ""
                short = search.get("shortDisplayName") or ""
                description = search.get("description") or ""
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

        matches.sort(key=lambda item: (-item["score"], item["displayName"]))
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


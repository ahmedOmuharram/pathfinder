"""WDK ID <-> local ID mapping and record-type resolution."""

from __future__ import annotations

from typing import cast

from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.integrations.veupathdb.discovery import get_discovery_service
from veupath_chatbot.platform.types import JSONObject, JSONValue

from .base import StrategyToolsBase


class IdMappingMixin(StrategyToolsBase):
    def _infer_record_type(self, step: PlanStepNode) -> str | None:
        # Plan steps no longer store record_type; prefer graph-level context when available.
        graph = self._get_graph(None)
        return graph.record_type if graph else None

    async def _resolve_record_type(self, record_type: str | None) -> str | None:
        if not record_type:
            return record_type
        discovery = get_discovery_service()
        record_types = await discovery.get_record_types(self.session.site_id)

        def normalize(value: str) -> str:
            return value.strip().lower()

        def rt_name(rt: str | JSONObject) -> str:
            if isinstance(rt, str):
                return rt
            if isinstance(rt, dict):
                url_seg_raw = rt.get("urlSegment")
                name_raw = rt.get("name")
                url_seg = url_seg_raw if isinstance(url_seg_raw, str) else None
                name = name_raw if isinstance(name_raw, str) else None
                return str(url_seg or name or "")
            return ""

        normalized = normalize(record_type)
        exact: list[JSONValue] = []
        for rt in record_types:
            if isinstance(rt, (str, dict)):
                if normalize(rt_name(rt)) == normalized:
                    exact.append(rt)
                elif isinstance(rt, dict):
                    name_raw = rt.get("name")
                    name = name_raw if isinstance(name_raw, str) else ""
                    if normalize(name) == normalized:
                        exact.append(rt)
        if exact:
            if isinstance(exact[0], str):
                return exact[0]
            exact_dict = exact[0] if isinstance(exact[0], dict) else {}
            return cast(
                str,
                exact_dict.get("urlSegment", exact_dict.get("name", record_type)),
            )

        display_matches: list[JSONObject] = []
        for rt in record_types:
            if not isinstance(rt, dict):
                continue
            display_name_raw = rt.get("displayName")
            display_name = display_name_raw if isinstance(display_name_raw, str) else ""
            if normalize(display_name) == normalized:
                display_matches.append(rt)
        if len(display_matches) == 1:
            match_dict = (
                display_matches[0] if isinstance(display_matches[0], dict) else {}
            )
            return cast(
                str,
                match_dict.get("urlSegment", match_dict.get("name", record_type)),
            )

        return record_type

    async def _resolve_record_type_for_search(
        self,
        record_type: str | None,
        search_name: str | None,
        require_match: bool = False,
        allow_fallback: bool = True,
    ) -> str | None:
        resolved = await self._resolve_record_type(record_type)
        if not search_name:
            return resolved
        discovery = get_discovery_service()
        record_types = await discovery.get_record_types(self.session.site_id)

        def matches(search: JSONValue) -> bool:
            if not isinstance(search, dict):
                return False
            url_seg_raw = search.get("urlSegment")
            name_raw = search.get("name")
            url_seg = url_seg_raw if isinstance(url_seg_raw, str) else None
            name = name_raw if isinstance(name_raw, str) else None
            return url_seg == search_name or name == search_name

        if resolved:
            try:
                searches = await discovery.get_searches(self.session.site_id, resolved)
                if any(matches(s) for s in searches):
                    return resolved
            except Exception:
                pass
            if not allow_fallback:
                return None if require_match else resolved

        if not allow_fallback:
            return None if require_match else resolved

        for rt in record_types:
            if isinstance(rt, str):
                rt_name = rt
            elif isinstance(rt, dict):
                rt_name = str(rt.get("urlSegment", rt.get("name", "")))
            else:
                continue
            if not rt_name:
                continue
            try:
                searches = await discovery.get_searches(self.session.site_id, rt_name)
            except Exception:
                continue
            if any(matches(s) for s in searches):
                return rt_name

        return None if require_match else resolved

    async def _find_record_type_hint(
        self, search_name: str, exclude: str | None = None
    ) -> str | None:
        discovery = get_discovery_service()
        try:
            record_types = await discovery.get_record_types(self.session.site_id)
        except Exception:
            return None

        def matches(search: JSONValue) -> bool:
            if not isinstance(search, dict):
                return False
            url_seg_raw = search.get("urlSegment")
            name_raw = search.get("name")
            url_seg = url_seg_raw if isinstance(url_seg_raw, str) else None
            name = name_raw if isinstance(name_raw, str) else None
            return url_seg == search_name or name == search_name

        for rt in record_types:
            if isinstance(rt, str):
                rt_name = rt
            elif isinstance(rt, dict):
                rt_name = str(rt.get("urlSegment", rt.get("name", "")))
            else:
                continue
            if not rt_name or (exclude and rt_name == exclude):
                continue
            try:
                searches = await discovery.get_searches(self.session.site_id, rt_name)
            except Exception:
                continue
            if any(matches(s) for s in searches):
                return rt_name
        return None

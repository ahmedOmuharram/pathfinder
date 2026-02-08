"""Helper methods for strategy tool implementations (service layer)."""

from __future__ import annotations

from typing import cast

from veupath_chatbot.domain.parameters.vocab_utils import (
    flatten_vocab,
    normalize_vocab_key,
)
from veupath_chatbot.domain.strategy.ast import PlanStepNode, StrategyAST
from veupath_chatbot.domain.strategy.explain import explain_operation
from veupath_chatbot.integrations.veupathdb.discovery import get_discovery_service
from veupath_chatbot.platform.errors import ErrorCode, ValidationError
from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue
from veupath_chatbot.services.strategy_session import StrategyGraph

from .base import StrategyToolsBase
from .graph_integrity import find_root_step_ids


class StrategyToolsHelpers(StrategyToolsBase):
    def _get_graph(self, graph_id: str | None) -> StrategyGraph | None:
        graph = self.session.get_graph(graph_id)
        if graph:
            return graph
        # Fallback to active graph if an invalid id was provided.
        return self.session.get_graph(None)

    def _graph_not_found(self, graph_id: str | None) -> JSONObject:
        if graph_id:
            return self._tool_error(
                ErrorCode.NOT_FOUND, "Graph not found", graphId=graph_id
            )
        return self._tool_error(
            ErrorCode.NOT_FOUND, "Graph not found. Provide a graphId.", graphId=graph_id
        )

    def _validation_error_payload(
        self, exc: ValidationError, **context: JSONValue
    ) -> JSONObject:
        details: JSONObject = {}
        if exc.detail:
            details["detail"] = exc.detail
        if exc.errors is not None:
            details["errors"] = exc.errors
            for error in exc.errors:
                if not isinstance(error, dict):
                    continue
                extra = error.get("context")
                if isinstance(extra, dict):
                    context.update({k: v for k, v in extra.items() if v is not None})
        details.update({k: v for k, v in context.items() if v is not None})
        return self._tool_error(ErrorCode.VALIDATION_ERROR, exc.title, **details)

    def _tool_error(
        self, code: ErrorCode | str, message: str, **details: JSONValue
    ) -> JSONObject:
        return tool_error(code, message, **details)

    def _is_placeholder_name(self, name: str | None) -> bool:
        if not name:
            return True
        return name.strip().lower() in {"draft graph", "draft strategy", "draft"}

    def _derive_strategy_name(
        self,
        record_type: str | None,
        root_step: PlanStepNode,
    ) -> str:
        base = None
        kind = root_step.infer_kind()
        if kind == "search" or kind == "transform":
            base = root_step.display_name or root_step.search_name
        elif kind == "combine":
            if root_step.operator is not None:
                base = root_step.display_name or explain_operation(root_step.operator)
            else:
                base = root_step.display_name
        base = (base or "").strip()
        if not base:
            base = f"{record_type.title()} strategy" if record_type else "Strategy"
        if record_type and record_type.lower() not in base.lower():
            base = f"{record_type.title()} - {base}"
        return base[:120]

    def _derive_strategy_description(
        self,
        record_type: str | None,
        root_step: PlanStepNode,
    ) -> str:
        kind = root_step.infer_kind()
        if kind == "search":
            summary = root_step.display_name or root_step.search_name
            verb = "Find"
        elif kind == "transform":
            summary = root_step.display_name or root_step.search_name
            verb = "Transform"
        else:
            if root_step.operator is not None:
                summary = explain_operation(root_step.operator)
            else:
                summary = root_step.display_name or "combine"
            verb = "Combine"
        summary = (summary or "").strip()
        if not summary:
            summary = "results"
        if record_type:
            return f"{verb} {record_type} results for {summary}."
        return f"{verb} results for {summary}."

    def _infer_record_type(self, step: PlanStepNode) -> str | None:
        # Plan steps no longer store record_type; prefer graph-level context when available.
        graph = self._get_graph(None)
        return graph.record_type if graph else None

    def _filter_search_options(
        self, searches: JSONArray, query: str, limit: int = 20
    ) -> list[str]:
        lowered = query.lower()
        results: list[str] = []
        for search in searches:
            if not isinstance(search, dict):
                continue
            name_raw = search.get("name") or search.get("urlSegment")
            name = name_raw if isinstance(name_raw, str) else ""
            display_raw = search.get("displayName")
            display = display_raw if isinstance(display_raw, str) else ""
            name_lower = name.lower() if isinstance(name, str) else ""
            display_lower = display.lower() if isinstance(display, str) else ""
            if lowered in name_lower or lowered in display_lower:
                result_value = name or display
                if result_value:
                    results.append(result_value)
            if len(results) >= limit:
                break
        return results

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

    def _extract_vocab_options(
        self, vocabulary: JSONObject, limit: int = 50
    ) -> list[str]:
        options: list[str] = []

        def walk(node: JSONObject) -> None:
            if len(options) >= limit:
                return
            data_raw = node.get("data")
            data = data_raw if isinstance(data_raw, dict) else {}
            display_raw = data.get("display")
            display = display_raw if isinstance(display_raw, str) else None
            if display and display != "@@fake@@":
                options.append(display)
            children_raw = node.get("children")
            children = children_raw if isinstance(children_raw, list) else []
            for child in children:
                if isinstance(child, dict):
                    walk(child)

        if vocabulary:
            walk(vocabulary)
        return options

    def _match_vocab_value(
        self, vocabulary: JSONObject | JSONArray, value: JSONValue
    ) -> str:
        if value is None:
            return ""
        target = str(value)
        if not target or not vocabulary:
            return target
        entries = flatten_vocab(vocabulary, prefer_term=False)
        for entry in entries:
            display = entry.get("display")
            raw_value = entry.get("value")
            if target == display:
                return raw_value or display or target
            if target == raw_value:
                return raw_value or target
        normalized_target = normalize_vocab_key(target)
        for entry in entries:
            display = entry.get("display")
            raw_value = entry.get("value")
            if display and normalize_vocab_key(display) == normalized_target:
                return raw_value or display
            if raw_value and normalize_vocab_key(raw_value) == normalized_target:
                return raw_value
        return target

    def _vocab_contains_value(self, vocabulary: JSONObject, value: str) -> bool:
        """Check if a vocabulary tree contains the value (display or value field)."""
        target = value.strip()
        if not target or not vocabulary:
            return False

        def walk(node: JSONObject) -> bool:
            data_raw = node.get("data")
            data = data_raw if isinstance(data_raw, dict) else {}
            display_raw = data.get("display")
            display = display_raw if isinstance(display_raw, str) else None
            value_raw = data.get("value")
            raw_value = value_raw if isinstance(value_raw, str) else None
            if target in (display, raw_value):
                return True
            children_raw = node.get("children")
            children = children_raw if isinstance(children_raw, list) else []
            return any(isinstance(child, dict) and walk(child) for child in children)

        return walk(vocabulary)

    def _get_vocab_node_value(self, node: JSONObject) -> str:
        data_raw = node.get("data")
        data = data_raw if isinstance(data_raw, dict) else {}
        value_raw = data.get("value")
        id_raw = data.get("id")
        term_raw = data.get("term")
        name_raw = data.get("name")
        display_raw = data.get("display")
        raw_value: str | None = None
        if isinstance(value_raw, str):
            raw_value = value_raw
        elif isinstance(id_raw, str):
            raw_value = id_raw
        elif isinstance(term_raw, str):
            raw_value = term_raw
        elif isinstance(name_raw, str):
            raw_value = name_raw
        elif isinstance(display_raw, str):
            raw_value = display_raw
        return raw_value if raw_value is not None else ""

    def _find_vocab_node_for_match(
        self, node: JSONObject, match: str
    ) -> JSONObject | None:
        data_raw = node.get("data")
        data = data_raw if isinstance(data_raw, dict) else {}
        value_raw = data.get("value")
        id_raw = data.get("id")
        term_raw = data.get("term")
        name_raw = data.get("name")
        display_raw = data.get("display")
        candidates: list[JSONValue] = []
        if value_raw is not None:
            candidates.append(value_raw)
        if id_raw is not None:
            candidates.append(id_raw)
        if term_raw is not None:
            candidates.append(term_raw)
        if name_raw is not None:
            candidates.append(name_raw)
        if display_raw is not None:
            candidates.append(display_raw)
        for candidate in candidates:
            if match == str(candidate):
                return node
        normalized = normalize_vocab_key(match)
        for candidate in candidates:
            if normalize_vocab_key(str(candidate)) == normalized:
                return node
        children_raw = node.get("children")
        children = children_raw if isinstance(children_raw, list) else []
        for child in children:
            if isinstance(child, dict):
                found = self._find_vocab_node_for_match(child, match)
                if found:
                    return found
        return None

    def _collect_leaf_terms(self, node: JSONObject) -> list[str]:
        children_raw = node.get("children")
        children = children_raw if isinstance(children_raw, list) else []
        if not children:
            value = self._get_vocab_node_value(node)
            return [value] if value else []
        leaves: list[str] = []
        for child in children:
            if isinstance(child, dict):
                leaves.extend(self._collect_leaf_terms(child))
        return leaves

    def _expand_leaf_values(
        self,
        vocabulary: JSONObject,
        values: list[str],
        include_parent: bool = False,
    ) -> list[str]:
        expanded: list[str] = []
        seen: set[str] = set()
        for value in values:
            match = str(value)
            if not match:
                continue
            node = self._find_vocab_node_for_match(vocabulary, match)
            if not node:
                if match not in seen:
                    seen.add(match)
                    expanded.append(match)
                continue
            if include_parent:
                parent_value = self._get_vocab_node_value(node)
                if parent_value and parent_value not in seen:
                    seen.add(parent_value)
                    expanded.append(parent_value)
            for leaf in self._collect_leaf_terms(node):
                if leaf and leaf not in seen:
                    seen.add(leaf)
                    expanded.append(leaf)
        return expanded

    def _serialize_step(
        self,
        graph: StrategyGraph,
        step: PlanStepNode,
    ) -> JSONObject:
        default_name = step.search_name
        info: JSONObject = {
            "graphId": graph.id,
            "graphName": graph.name,
            "stepId": step.id,
            "displayName": step.display_name or default_name,
            "recordType": graph.record_type,
        }
        kind = step.infer_kind()
        info["kind"] = kind
        # `searchName` is only meaningful for WDK-backed question steps (leaf / transform).
        # Combine steps are represented structurally (primary/secondary/operator) and do not
        # correspond to a WDK "searchName" that the UI can load param metadata for.
        if kind != "combine":
            info["searchName"] = step.search_name
        info["parameters"] = step.parameters
        if kind == "combine":
            info["operator"] = step.operator.value if step.operator else None
            info["primaryInputStepId"] = (
                step.primary_input.id if step.primary_input else None
            )
            info["secondaryInputStepId"] = (
                step.secondary_input.id if step.secondary_input else None
            )
        elif kind == "transform":
            info["primaryInputStepId"] = (
                step.primary_input.id if step.primary_input else None
            )
        info["filters"] = [f.to_dict() for f in getattr(step, "filters", []) or []]
        info["analyses"] = [a.to_dict() for a in getattr(step, "analyses", []) or []]
        info["reports"] = [r.to_dict() for r in getattr(step, "reports", []) or []]
        return info

    def _serialize_graph_step(self, step: PlanStepNode) -> JSONObject:
        kind = step.infer_kind()
        default_name = step.search_name
        base: JSONObject = {
            "id": step.id,
            "kind": kind,
            "displayName": step.display_name or default_name,
            "recordType": graph.record_type
            if (graph := self._get_graph(None))
            else None,
        }
        # Same rule as `_serialize_step`: only emit `searchName` for non-combine nodes.
        if kind != "combine":
            base["searchName"] = step.search_name
        base["parameters"] = step.parameters
        base["primaryInputStepId"] = (
            step.primary_input.id if step.primary_input else None
        )
        base["secondaryInputStepId"] = (
            step.secondary_input.id if step.secondary_input else None
        )
        if kind == "combine":
            base["operator"] = step.operator.value if step.operator else None
        base["filters"] = [f.to_dict() for f in getattr(step, "filters", []) or []]
        base["analyses"] = [a.to_dict() for a in getattr(step, "analyses", []) or []]
        base["reports"] = [r.to_dict() for r in getattr(step, "reports", []) or []]
        return base

    def _build_graph_snapshot(self, graph: StrategyGraph) -> JSONObject:
        plan_payload = self._build_context_plan(graph)
        record_type = plan_payload.get("recordType") if plan_payload else None
        name = plan_payload.get("name") if plan_payload else graph.name
        description = plan_payload.get("description") if plan_payload else None
        # rootStepId should only be set when the working graph has exactly
        # one output (one root). Do not guess based on "last_step_id" when multiple
        # roots exist, otherwise the UI/agent may incorrectly assume the strategy is done.
        roots = find_root_step_ids(graph)
        root_step_id = roots[0] if len(roots) == 1 else None

        steps = [self._serialize_graph_step(step) for step in graph.steps.values()]
        edges: JSONArray = []
        for step in graph.steps.values():
            primary_input = getattr(step, "primary_input", None)
            if primary_input is not None:
                edges.append(
                    {
                        "sourceId": primary_input.id,
                        "targetId": step.id,
                        "kind": "primary",
                    }
                )
            secondary_input = getattr(step, "secondary_input", None)
            if secondary_input is not None:
                edges.append(
                    {
                        "sourceId": secondary_input.id,
                        "targetId": step.id,
                        "kind": "secondary",
                    }
                )

        return {
            "graphId": graph.id,
            "graphName": graph.name,
            "recordType": record_type,
            "name": name,
            "description": description,
            "rootStepId": root_step_id,
            "steps": cast(JSONValue, steps),
            "edges": edges,
        }

    def _build_context_plan(self, graph: StrategyGraph) -> JSONObject | None:
        if not graph.last_step_id:
            return None
        root_step = graph.get_step(graph.last_step_id)
        if not root_step:
            return None
        record_type = graph.record_type
        if not record_type:
            return None
        name = graph.current_strategy.name if graph.current_strategy else graph.name
        description = (
            graph.current_strategy.description if graph.current_strategy else None
        )
        if self._is_placeholder_name(name):
            name = self._derive_strategy_name(record_type, root_step)
        if not description:
            description = self._derive_strategy_description(record_type, root_step)
        strategy = StrategyAST(
            record_type=record_type,
            root=root_step,
            name=name,
            description=description,
        )
        graph.current_strategy = strategy
        graph.name = name or graph.name
        return {
            "graphId": graph.id,
            "graphName": graph.name,
            "plan": strategy.to_dict(),
            "recordType": record_type,
            "name": name,
            "description": description,
        }

    def _with_plan_payload(
        self, graph: StrategyGraph, payload: JSONObject
    ) -> JSONObject:
        plan_payload = self._build_context_plan(graph)
        if plan_payload:
            payload.update(plan_payload)
        else:
            payload.setdefault("graphId", graph.id)
            payload.setdefault("graphName", graph.name)
        return payload

    def _with_full_graph(self, graph: StrategyGraph, payload: JSONObject) -> JSONObject:
        response = self._with_plan_payload(graph, payload)
        response["graphSnapshot"] = self._build_graph_snapshot(graph)
        return response

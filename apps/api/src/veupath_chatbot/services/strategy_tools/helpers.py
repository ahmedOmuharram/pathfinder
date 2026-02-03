"""Helper methods for strategy tool implementations (service layer)."""

from __future__ import annotations

from typing import Any

from veupath_chatbot.platform.errors import ErrorCode, ValidationError
from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.domain.parameters.vocab_utils import flatten_vocab, normalize_vocab_key
from veupath_chatbot.domain.strategy.ast import PlanStepNode, StrategyAST
from veupath_chatbot.domain.strategy.explain import explain_operation
from veupath_chatbot.services.strategy_session import StrategyGraph
from veupath_chatbot.integrations.veupathdb.discovery import get_discovery_service

from .base import StrategyToolsBase
from .graph_integrity import find_root_step_ids


class StrategyToolsHelpers(StrategyToolsBase):
    def _get_graph(self, graph_id: str | None) -> StrategyGraph | None:
        graph = self.session.get_graph(graph_id)
        if graph:
            return graph
        # Fallback to active graph if an invalid id was provided.
        return self.session.get_graph(None)

    def _graph_not_found(self, graph_id: str | None) -> dict[str, Any]:
        if graph_id:
            return self._tool_error(
                ErrorCode.NOT_FOUND, "Graph not found", graphId=graph_id
            )
        return self._tool_error(
            ErrorCode.NOT_FOUND, "Graph not found. Provide a graphId.", graphId=graph_id
        )

    def _validation_error_payload(
        self, exc: ValidationError, **context: Any
    ) -> dict[str, Any]:
        details: dict[str, Any] = {}
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

    def _tool_error(self, code: ErrorCode | str, message: str, **details: Any) -> dict[str, Any]:
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
        if kind == "search":
            base = root_step.display_name or root_step.search_name
        elif kind == "transform":
            base = root_step.display_name or root_step.search_name
        elif kind == "combine":
            base = root_step.display_name or explain_operation(root_step.operator)  # type: ignore[arg-type]
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
            summary = explain_operation(root_step.operator)  # type: ignore[arg-type]
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
        self, searches: list[dict[str, Any]], query: str, limit: int = 20
    ) -> list[str]:
        lowered = query.lower()
        results = []
        for search in searches:
            name = search.get("name") or search.get("urlSegment") or ""
            display = search.get("displayName") or ""
            if lowered in name.lower() or lowered in display.lower():
                results.append(name or display)
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

        def rt_name(rt: Any) -> str:
            if isinstance(rt, str):
                return rt
            return rt.get("urlSegment") or rt.get("name") or ""

        normalized = normalize(record_type)
        exact = [
            rt
            for rt in record_types
            if normalize(rt_name(rt)) == normalized
            or (isinstance(rt, dict) and normalize(rt.get("name", "")) == normalized)
        ]
        if exact:
            if isinstance(exact[0], str):
                return exact[0]
            return exact[0].get("urlSegment", exact[0].get("name", record_type))

        display_matches = [
            rt
            for rt in record_types
            if isinstance(rt, dict) and normalize(rt.get("displayName", "")) == normalized
        ]
        if len(display_matches) == 1:
            return display_matches[0].get(
                "urlSegment", display_matches[0].get("name", record_type)
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

        def matches(search: dict[str, Any]) -> bool:
            return (
                search.get("urlSegment") == search_name
                or search.get("name") == search_name
            )

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
            rt_name = rt if isinstance(rt, str) else rt.get("urlSegment", rt.get("name", ""))
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

        def matches(search: dict[str, Any]) -> bool:
            return (
                search.get("urlSegment") == search_name
                or search.get("name") == search_name
            )

        for rt in record_types:
            rt_name = rt if isinstance(rt, str) else rt.get("urlSegment", rt.get("name", ""))
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
        self, vocabulary: dict[str, Any], limit: int = 50
    ) -> list[str]:
        options: list[str] = []

        def walk(node: dict[str, Any]) -> None:
            if len(options) >= limit:
                return
            data = node.get("data", {})
            display = data.get("display")
            if display and display != "@@fake@@":
                options.append(str(display))
            for child in node.get("children", []) or []:
                walk(child)

        if vocabulary:
            walk(vocabulary)
        return options

    def _match_vocab_value(
        self, vocabulary: dict[str, Any] | list[Any], value: Any
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

    def _vocab_contains_value(self, vocabulary: dict[str, Any], value: str) -> bool:
        """Check if a vocabulary tree contains the value (display or value field)."""
        target = value.strip()
        if not target or not vocabulary:
            return False

        def walk(node: dict[str, Any]) -> bool:
            data = node.get("data", {})
            display = data.get("display")
            raw_value = data.get("value")
            if target == display or target == raw_value:
                return True
            for child in node.get("children", []) or []:
                if walk(child):
                    return True
            return False

        return walk(vocabulary)

    def _get_vocab_node_value(self, node: dict[str, Any]) -> str:
        data = node.get("data", {})
        raw_value = (
            data.get("value")
            or data.get("id")
            or data.get("term")
            or data.get("name")
            or data.get("display")
        )
        return str(raw_value) if raw_value is not None else ""

    def _find_vocab_node_for_match(
        self, node: dict[str, Any], match: str
    ) -> dict[str, Any] | None:
        data = node.get("data", {})
        candidates = [
            data.get("value"),
            data.get("id"),
            data.get("term"),
            data.get("name"),
            data.get("display"),
        ]
        for candidate in candidates:
            if candidate is None:
                continue
            if match == str(candidate):
                return node
        normalized = normalize_vocab_key(match)
        for candidate in candidates:
            if candidate is None:
                continue
            if normalize_vocab_key(str(candidate)) == normalized:
                return node
        for child in node.get("children", []) or []:
            found = self._find_vocab_node_for_match(child, match)
            if found:
                return found
        return None

    def _collect_leaf_terms(self, node: dict[str, Any]) -> list[str]:
        children = node.get("children", []) or []
        if not children:
            value = self._get_vocab_node_value(node)
            return [value] if value else []
        leaves: list[str] = []
        for child in children:
            leaves.extend(self._collect_leaf_terms(child))
        return leaves

    def _expand_leaf_values(
        self, vocabulary: dict[str, Any], values: list[str], include_parent: bool = False
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
    ) -> dict[str, Any]:
        default_name = step.search_name
        info: dict[str, Any] = {
            "graphId": graph.id,
            "graphName": graph.name,
            "stepId": step.id,
            "displayName": step.display_name or default_name,
            "recordType": graph.record_type,
        }
        kind = step.infer_kind()
        info["kind"] = kind
        info["searchName"] = step.search_name
        info["parameters"] = step.parameters
        if kind == "combine":
            info["operator"] = step.operator.value if step.operator else None
            info["primaryInputStepId"] = step.primary_input.id if step.primary_input else None
            info["secondaryInputStepId"] = (
                step.secondary_input.id if step.secondary_input else None
            )
        elif kind == "transform":
            info["primaryInputStepId"] = step.primary_input.id if step.primary_input else None
        info["filters"] = [f.to_dict() for f in getattr(step, "filters", []) or []]
        info["analyses"] = [a.to_dict() for a in getattr(step, "analyses", []) or []]
        info["reports"] = [r.to_dict() for r in getattr(step, "reports", []) or []]
        return info

    def _serialize_graph_step(self, step: PlanStepNode) -> dict[str, Any]:
        kind = step.infer_kind()
        default_name = step.search_name
        base: dict[str, Any] = {
            "id": step.id,
            "kind": kind,
            "displayName": step.display_name or default_name,
            "recordType": graph.record_type if (graph := self._get_graph(None)) else None,
        }
        base["searchName"] = step.search_name
        base["parameters"] = step.parameters
        base["primaryInputStepId"] = step.primary_input.id if step.primary_input else None
        base["secondaryInputStepId"] = (
            step.secondary_input.id if step.secondary_input else None
        )
        if kind == "combine":
            base["operator"] = step.operator.value if step.operator else None
        base["filters"] = [f.to_dict() for f in getattr(step, "filters", []) or []]
        base["analyses"] = [a.to_dict() for a in getattr(step, "analyses", []) or []]
        base["reports"] = [r.to_dict() for r in getattr(step, "reports", []) or []]
        return base

    def _build_graph_snapshot(self, graph: StrategyGraph) -> dict[str, Any]:
        plan_payload = self._build_context_plan(graph)
        record_type = plan_payload.get("recordType") if plan_payload else None
        name = plan_payload.get("name") if plan_payload else graph.name
        description = plan_payload.get("description") if plan_payload else None
        # IMPORTANT: rootStepId should only be set when the working graph has exactly
        # one output (one root). Do not guess based on "last_step_id" when multiple
        # roots exist, otherwise the UI/agent may incorrectly assume the strategy is done.
        roots = find_root_step_ids(graph)
        root_step_id = roots[0] if len(roots) == 1 else None

        steps = [self._serialize_graph_step(step) for step in graph.steps.values()]
        edges: list[dict[str, Any]] = []
        for step in graph.steps.values():
            if getattr(step, "primary_input", None) is not None:
                edges.append(
                    {
                        "sourceId": step.primary_input.id,
                        "targetId": step.id,
                        "kind": "primary",
                    }
                )
            if getattr(step, "secondary_input", None) is not None:
                edges.append(
                    {
                        "sourceId": step.secondary_input.id,
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
            "steps": steps,
            "edges": edges,
        }

    def _build_context_plan(self, graph: StrategyGraph) -> dict[str, Any] | None:
        if not graph.last_step_id:
            return None
        root_step = graph.get_step(graph.last_step_id)
        if not root_step:
            return None
        record_type = graph.record_type
        if not record_type:
            return None
        name = graph.current_strategy.name if graph.current_strategy else graph.name
        description = graph.current_strategy.description if graph.current_strategy else None
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

    def _with_plan_payload(self, graph: StrategyGraph, payload: dict[str, Any]) -> dict[str, Any]:
        plan_payload = self._build_context_plan(graph)
        if plan_payload:
            payload.update(plan_payload)
        else:
            payload.setdefault("graphId", graph.id)
            payload.setdefault("graphName", graph.name)
        return payload

    def _with_full_graph(self, graph: StrategyGraph, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._with_plan_payload(graph, payload)
        response["graphSnapshot"] = self._build_graph_snapshot(graph)
        return response


"""Graph traversal, node/edge operations, serialization, and snapshots."""

from __future__ import annotations

from typing import cast

from veupath_chatbot.domain.strategy.ast import PlanStepNode, StrategyAST
from veupath_chatbot.domain.strategy.explain import explain_operation
from veupath_chatbot.domain.strategy.session import StrategyGraph
from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue

from .base import StrategyToolsBase
from .graph_integrity import find_root_step_ids


class GraphOpsMixin(StrategyToolsBase):
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

    def _serialize_step(
        self,
        graph: StrategyGraph,
        step: PlanStepNode,
    ) -> JSONObject:
        """Serialize a step with WDK-aligned fields.

        Includes ``estimatedSize`` and ``wdkStepId`` when available on the
        graph (populated after ``build_strategy``).  Omits noisy fields
        (parameters, filters, analyses, reports) when empty.

        :param graph: Strategy graph with WDK IDs and counts.
        :param step: Step node to serialize.
        :returns: Serialized step dict.
        """
        kind = step.infer_kind()
        info: JSONObject = {
            "stepId": step.id,
            "kind": kind,
            "displayName": step.display_name or step.search_name,
        }

        # searchName is only meaningful for leaf / transform steps.
        if kind != "combine":
            info["searchName"] = step.search_name

        # Structural relationships.
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

        # WDK-aligned fields (populated after build_strategy).
        wdk_step_id = graph.wdk_step_ids.get(step.id)
        if wdk_step_id is not None:
            info["wdkStepId"] = wdk_step_id
        info["isBuilt"] = wdk_step_id is not None

        estimated_size = graph.step_counts.get(step.id)
        if estimated_size is not None:
            info["estimatedSize"] = estimated_size

        # Only include heavy fields when non-empty.
        if step.parameters:
            info["parameters"] = step.parameters
        filters = [f.to_dict() for f in getattr(step, "filters", []) or []]
        if filters:
            info["filters"] = filters
        analyses = [a.to_dict() for a in getattr(step, "analyses", []) or []]
        if analyses:
            info["analyses"] = analyses
        reports = [r.to_dict() for r in getattr(step, "reports", []) or []]
        if reports:
            info["reports"] = reports
        return info

    def _serialize_graph_step(self, step: PlanStepNode) -> JSONObject:
        """Serialize a step for graph snapshots.

        Same enrichments as ``_serialize_step`` (WDK IDs, counts) but keyed
        by ``id`` instead of ``stepId`` for graph-snapshot compatibility.

        :param step: Step node to serialize.
        :returns: Serialized step dict keyed by id.
        """
        graph = self._get_graph(None)
        kind = step.infer_kind()
        base: JSONObject = {
            "id": step.id,
            "kind": kind,
            "displayName": step.display_name or step.search_name,
        }
        if kind != "combine":
            base["searchName"] = step.search_name

        base["primaryInputStepId"] = (
            step.primary_input.id if step.primary_input else None
        )
        base["secondaryInputStepId"] = (
            step.secondary_input.id if step.secondary_input else None
        )
        if kind == "combine":
            base["operator"] = step.operator.value if step.operator else None

        # WDK-aligned fields (populated after build_strategy).
        if graph:
            wdk_step_id = graph.wdk_step_ids.get(step.id)
            if wdk_step_id is not None:
                base["wdkStepId"] = wdk_step_id
            base["isBuilt"] = wdk_step_id is not None
            estimated_size = graph.step_counts.get(step.id)
            if estimated_size is not None:
                base["estimatedSize"] = estimated_size

        # Only include heavy fields when non-empty.
        if step.parameters:
            base["parameters"] = step.parameters
        filters = [f.to_dict() for f in getattr(step, "filters", []) or []]
        if filters:
            base["filters"] = filters
        analyses = [a.to_dict() for a in getattr(step, "analyses", []) or []]
        if analyses:
            base["analyses"] = analyses
        reports = [r.to_dict() for r in getattr(step, "reports", []) or []]
        if reports:
            base["reports"] = reports
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
        # Prefer the single subtree root from graph.roots; fall back to
        # last_step_id when roots is ambiguous or not yet populated.
        if len(graph.roots) == 1:
            root_id = next(iter(graph.roots))
        elif graph.last_step_id:
            root_id = graph.last_step_id
        else:
            return None
        root_step = graph.get_step(root_id)
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

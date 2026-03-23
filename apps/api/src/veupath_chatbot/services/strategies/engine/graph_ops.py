"""Graph traversal, node/edge operations, serialization, and snapshots."""

from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.domain.strategy.explain import explain_operation
from veupath_chatbot.domain.strategy.session import StrategyGraph
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKValidation
from veupath_chatbot.platform.pydantic_base import CamelModel
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.transport.http.schemas.sse import GraphSnapshotContent
from veupath_chatbot.transport.http.schemas.steps import StepResponse

from .base import StrategyToolsBase
from .graph_integrity import find_root_step_ids


class GraphEdge(CamelModel):
    """A single edge in a graph snapshot."""

    source_id: str
    target_id: str
    kind: str


class ContextPlanPayload(CamelModel):
    """Typed payload returned by _build_context_plan."""

    graph_id: str
    graph_name: str | None = None
    plan: JSONObject
    record_type: str
    name: str | None = None
    description: str | None = None


class GraphOpsMixin(StrategyToolsBase):
    def _derive_strategy_name(
        self,
        record_type: str | None,
        root_step: PlanStepNode,
    ) -> str:
        base = None
        kind = root_step.infer_kind()
        if kind in {"search", "transform"}:
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

    def _build_step_response(
        self,
        graph: StrategyGraph | None,
        step: PlanStepNode,
    ) -> StepResponse:
        """Build a StepResponse from a PlanStepNode + graph enrichment."""
        wdk_step_id: int | None = None
        validation: WDKValidation | None = None
        estimated_size: int | None = None
        record_type: str | None = None

        if graph:
            record_type = graph.record_type
            wdk_step_id = graph.wdk_step_ids.get(step.id)
            validation = graph.step_validations.get(step.id)
            count = graph.step_counts.get(step.id)
            if isinstance(count, int):
                estimated_size = count

        return StepResponse(
            id=step.id,
            kind=step.infer_kind(),
            display_name=step.display_name or step.search_name,
            search_name=step.search_name,
            record_type=record_type,
            parameters=step.parameters or None,
            operator=step.operator.value if step.operator else None,
            colocation_params=step.colocation_params,
            primary_input_step_id=step.primary_input.id if step.primary_input else None,
            secondary_input_step_id=step.secondary_input.id
            if step.secondary_input
            else None,
            estimated_size=estimated_size,
            wdk_step_id=wdk_step_id,
            is_built=wdk_step_id is not None,
            is_filtered=bool(step.filters),
            validation=validation,
            filters=step.filters or None,
            analyses=step.analyses or None,
            reports=step.reports or None,
        )

    def _serialize_step(self, graph: StrategyGraph, step: PlanStepNode) -> JSONObject:
        """Serialize a step for AI tool responses."""
        return self._build_step_response(graph, step).model_dump(
            by_alias=True, exclude_none=True, mode="json"
        )

    def _build_graph_snapshot(self, graph: StrategyGraph) -> JSONObject:
        ctx = self._build_context_plan(graph)
        roots = find_root_step_ids(graph)

        steps = [
            self._build_step_response(graph, step).model_dump(
                by_alias=True, exclude_none=True, mode="json"
            )
            for step in graph.steps.values()
        ]
        edges = [
            GraphEdge(source_id=inp.id, target_id=step.id, kind=kind).model_dump(
                by_alias=True, exclude_none=True, mode="json"
            )
            for step in graph.steps.values()
            for kind, inp in [
                ("primary", step.primary_input),
                ("secondary", step.secondary_input),
            ]
            if inp is not None
        ]

        return GraphSnapshotContent(
            graph_id=graph.id,
            graph_name=graph.name,
            record_type=ctx.record_type if ctx else None,
            name=ctx.name if ctx else graph.name,
            description=ctx.description if ctx else None,
            root_step_id=roots[0] if len(roots) == 1 else None,
            steps=steps,
            edges=edges,
            plan=ctx.plan if ctx else None,
        ).model_dump(by_alias=True, exclude_none=True, mode="json")

    def _build_context_plan(self, graph: StrategyGraph) -> ContextPlanPayload | None:
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
        name = graph.name
        description = graph.description
        if self._is_placeholder_name(name):
            name = self._derive_strategy_name(record_type, root_step)
        if not description:
            description = self._derive_strategy_description(record_type, root_step)
        graph.name = name or graph.name
        graph.description = description
        plan = graph.to_plan(root_id)
        if not plan:
            return None
        # Ensure description is in the plan dict
        if description:
            plan["description"] = description
        return ContextPlanPayload(
            graph_id=graph.id,
            graph_name=graph.name,
            plan=plan,
            record_type=record_type,
            name=name,
            description=description,
        )

    def _step_ok_response(self, graph: StrategyGraph, step: PlanStepNode) -> JSONObject:
        """Serialize a step as an ``ok=True`` response with a full graph snapshot.

        This combines the three-step pattern used after successful step
        mutations: serialize the step, mark ok, wrap with graph context.
        """
        response = self._serialize_step(graph, step)
        response["ok"] = True
        return self._with_full_graph(graph, response)

    def _with_plan_payload(
        self, graph: StrategyGraph, payload: JSONObject
    ) -> JSONObject:
        plan_payload = self._build_context_plan(graph)
        if plan_payload:
            payload.update(plan_payload.model_dump(by_alias=True, exclude_none=True))
        else:
            payload.setdefault("graphId", graph.id)
            payload.setdefault("graphName", graph.name)
        return payload

    def _with_full_graph(self, graph: StrategyGraph, payload: JSONObject) -> JSONObject:
        response = self._with_plan_payload(graph, payload)
        response["graphSnapshot"] = self._build_graph_snapshot(graph)
        return response

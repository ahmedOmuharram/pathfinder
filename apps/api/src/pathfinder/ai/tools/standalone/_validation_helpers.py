"""Validation helpers for strategy tool implementations.

Error payloads, graph/step lookup, and validation utilities.
"""

from pydantic import BaseModel, ConfigDict, Field

from pathfinder.domain.strategy.ast import PlanStepNode
from pathfinder.domain.strategy.session import StrategyGraph, StrategySession
from pathfinder.platform.errors import ErrorCode, ValidationError
from pathfinder.platform.event_schemas import GraphSnapshotContent
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.platform.tool_errors import ToolErrorPayload, tool_error
from pathfinder.platform.types import JSONObject, JSONValue
from pathfinder.services.strategies.schemas import StepResponse

# ---------------------------------------------------------------------------
# Private parsing model (replace isinstance/dict.get chains per CLAUDE.md)
# ---------------------------------------------------------------------------


class _ValidationErrorEntry(BaseModel):
    """A single entry in a ``ValidationError.errors`` list."""

    model_config = ConfigDict(extra="ignore")
    context: dict[str, JSONValue] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Models (used by tool modules)
# ---------------------------------------------------------------------------


class ContextPlanPayload(CamelModel):
    """Typed payload returned by build_context_plan."""

    graph_id: str
    graph_name: str | None = None
    plan: JSONObject
    record_type: str
    name: str | None = None
    description: str | None = None


class StepOkResponse(CamelModel):
    """Typed response for successful step mutations."""

    ok: bool = True
    step: StepResponse
    graph_id: str
    graph_name: str | None = None
    record_type: str | None = None
    name: str | None = None
    description: str | None = None
    plan: JSONObject | None = None
    graph_snapshot: GraphSnapshotContent


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def get_graph(session: StrategySession, graph_id: str | None) -> StrategyGraph | None:
    graph = session.get_graph(graph_id)
    if graph:
        return graph
    # Fallback to active graph if an invalid id was provided.
    return session.get_graph(None)


def graph_not_found(graph_id: str | None) -> ToolErrorPayload:
    if graph_id:
        return tool_error(ErrorCode.NOT_FOUND, "Graph not found", graphId=graph_id)
    return tool_error(
        ErrorCode.NOT_FOUND, "Graph not found. Provide a graphId.", graphId=graph_id
    )


def step_not_found(step_id: str) -> ToolErrorPayload:
    """Standard error payload for a missing step."""
    return tool_error(
        ErrorCode.STEP_NOT_FOUND, f"Step not found: {step_id}", stepId=step_id
    )


def get_graph_and_step(
    session: StrategySession, graph_id: str | None, step_id: str
) -> tuple[StrategyGraph, PlanStepNode] | ToolErrorPayload:
    """Look up graph and step, returning an error payload on failure.

    Callers should check ``isinstance(result, ToolErrorPayload)`` -- if
    True the result is a ready-to-return error payload.  Otherwise it is
    a ``(graph, step)`` tuple.
    """
    graph = get_graph(session, graph_id)
    if not graph:
        return graph_not_found(graph_id)
    step = graph.get_step(step_id)
    if not step:
        return step_not_found(step_id)
    return graph, step


def validation_error_payload(
    exc: ValidationError, **context: JSONValue
) -> ToolErrorPayload:
    details: JSONObject = {}
    if exc.detail:
        details["detail"] = exc.detail
    if exc.errors is not None:
        details["errors"] = exc.errors
        for raw_error in exc.errors:
            parsed = _ValidationErrorEntry.model_validate(raw_error)
            context.update(
                {k: v for k, v in parsed.context.items() if v is not None}
            )
    details.update({k: v for k, v in context.items() if v is not None})
    return tool_error(ErrorCode.VALIDATION_ERROR, exc.title, **details)


def is_placeholder_name(name: str | None) -> bool:
    if not name:
        return True
    return name.strip().lower() in {
        "draft graph",
        "draft strategy",
        "draft",
        "new conversation",
    }

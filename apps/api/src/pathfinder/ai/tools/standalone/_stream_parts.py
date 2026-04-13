"""Helpers for building ``DataChunk`` / ``SourceUrlChunk`` entries from
PathFinder domain objects.

These build the ``ToolReturn.metadata`` payloads emitted by tools in the
new AI SDK v6 streaming protocol. Each helper maps internal domain state
onto a typed ``shared_py.stream_parts.*`` payload model, then wraps the
JSON-serialized model in a ``DataChunk`` with the conventional
``data-<name>`` type.

Only ``DataChunk``, ``SourceUrlChunk``, ``SourceDocumentChunk``, and
``FileChunk`` survive adapter filtering into the client stream. All other
chunk shapes placed in ``ToolReturn.metadata`` are dropped silently — so
never put ``StartChunk`` / ``FinishChunk`` / ``MessageMetadataChunk``
here.
"""

from __future__ import annotations

from pydantic_ai.ui.vercel_ai.response_types import (
    DataChunk,
    SourceUrlChunk,
)
from shared_py.stream_parts.conversation import ConversationTitle
from shared_py.stream_parts.gene_set import GeneSet as GeneSetPart
from shared_py.stream_parts.graph import (
    GraphCleared,
    GraphEdge,
    GraphEdgeOperator,
    GraphNode,
    GraphSnapshot,
)
from shared_py.stream_parts.plan import DecisionPresented, PlanArtifact, PlannedStep
from shared_py.stream_parts.problem_frame import ProblemFrame as ProblemFramePart
from shared_py.stream_parts.strategy import (
    StrategyLink,
    StrategyMeta,
    StrategyOperation,
    StrategyPatch,
)

from pathfinder.ai.orchestration.phase_results import ProblemFrame
from pathfinder.ai.tools.standalone._graph_helpers import build_step_response
from pathfinder.domain.strategy.ast import PlanStepNode
from pathfinder.domain.strategy.session import StrategyGraph, StrategySession
from pathfinder.domain.strategy.types import SyncStateProtocol
from pathfinder.platform.pydantic_base import CamelModel

# ── Operator coercion ──────────────────────────────────────────────────────


# Maps upper-cased input values to the canonical WDK operator Literal values
# defined on ``shared_py.stream_parts.graph.GraphEdgeOperator``. The dict
# structure lets mypy narrow the returned value to the Literal set without
# a ``cast`` or ``type: ignore``.
_OPERATOR_MAP: dict[str, GraphEdgeOperator] = {
    "INTERSECT": "INTERSECT",
    "UNION": "UNION",
    "MINUS": "MINUS",
    "RMINUS": "RMINUS",
    "LONLY": "LONLY",
    "RONLY": "RONLY",
    "COLOCATE": "COLOCATE",
}


def _coerce_operator(op: str | None) -> GraphEdgeOperator | None:
    """Return a stream-part-compatible operator or ``None`` if unknown.

    Matches the frontend/WDK canonical 7-operator set in
    ``shared_py.stream_parts.graph.GraphEdgeOperator``.
    """
    if op is None:
        return None
    return _OPERATOR_MAP.get(op.upper())


# ── Graph snapshot ─────────────────────────────────────────────────────────


def _count_for_step(
    step_id: str, sync_state: SyncStateProtocol | None
) -> int:
    """Safe lookup of estimated size for a step, default 0."""
    if sync_state is None:
        return 0
    count = sync_state.step_counts.get(step_id)
    return count if isinstance(count, int) else 0


def _snapshot_nodes(graph: StrategyGraph) -> list[GraphNode]:
    sync_state = None
    # A graph is only wired to a session for read-only purposes; in tools
    # that call this helper we always fetch sync_state through the session.
    return [
        GraphNode(
            id=step.id,
            search_name=step.search_name,
            estimated_size=_count_for_step(step.id, sync_state),
        )
        for step in graph.steps.values()
    ]


def _snapshot_edges(graph: StrategyGraph) -> list[GraphEdge]:
    edges: list[GraphEdge] = []
    for step in graph.steps.values():
        # Primary input edge
        primary = step.primary_input
        if primary is not None:
            edges.append(
                GraphEdge(
                    source=primary.id,
                    target=step.id,
                    operator=_coerce_operator(
                        step.operator.value if step.operator else None
                    ),
                )
            )
        # Secondary input edge
        secondary = step.secondary_input
        if secondary is not None:
            edges.append(
                GraphEdge(
                    source=secondary.id,
                    target=step.id,
                    operator=_coerce_operator(
                        step.operator.value if step.operator else None
                    ),
                )
            )
    return edges


def build_graph_snapshot_payload(
    session: StrategySession,
    graph: StrategyGraph,
) -> GraphSnapshot:
    """Build a ``GraphSnapshot`` stream-part payload for the current graph."""
    sync_state = session.sync_state
    total_genes = 0
    for root_id in graph.roots:
        total_genes += _count_for_step(root_id, sync_state)
    nodes = [
        GraphNode(
            id=step.id,
            search_name=step.search_name,
            estimated_size=_count_for_step(step.id, sync_state),
        )
        for step in graph.steps.values()
    ]
    edges = _snapshot_edges(graph)
    return GraphSnapshot(
        strategy_id=graph.id,
        gene_count=total_genes,
        nodes=nodes,
        edges=edges,
    )


def graph_snapshot_chunk(
    session: StrategySession, graph: StrategyGraph
) -> DataChunk:
    """Build the ``data-graph-snapshot`` DataChunk for a graph."""
    payload = build_graph_snapshot_payload(session, graph)
    return DataChunk(
        type="data-graph-snapshot",
        data=payload.model_dump(by_alias=True, mode="json"),
    )


def graph_cleared_chunk(*, reason: str | None = None) -> DataChunk:
    """Build the ``data-graph-cleared`` DataChunk."""
    payload = GraphCleared(reason=reason)
    return DataChunk(
        type="data-graph-cleared",
        data=payload.model_dump(by_alias=True, mode="json"),
    )


# ── Strategy patches and metadata ──────────────────────────────────────────


def _step_payload(
    graph: StrategyGraph,
    step: PlanStepNode,
    sync_state: SyncStateProtocol | None,
) -> dict[str, object]:
    """Serialize a step to the wire shape used in a StrategyPatch.step field.

    Deliberately keeps the existing ``StepResponse`` shape to match what the
    frontend already consumes for tool-result update events.
    """
    return build_step_response(graph, step, sync_state).model_dump(
        by_alias=True, exclude_none=True, mode="json"
    )


def strategy_patch_chunk(
    graph: StrategyGraph,
    step: PlanStepNode,
    *,
    operation: StrategyOperation,
    sync_state: SyncStateProtocol | None,
) -> DataChunk:
    """Build the ``data-strategy-update`` DataChunk for an add/update/remove."""
    payload = StrategyPatch(
        strategy_id=graph.id,
        operation=operation,
        step=_step_payload(graph, step, sync_state),
    )
    return DataChunk(
        type="data-strategy-update",
        data=payload.model_dump(by_alias=True, mode="json"),
    )


def strategy_remove_chunk(
    graph: StrategyGraph,
    step_id: str,
) -> DataChunk:
    """Build the ``data-strategy-update`` DataChunk for a remove_step op.

    Uses a minimal step payload (just the id) because the step is gone.
    """
    payload = StrategyPatch(
        strategy_id=graph.id,
        operation="remove_step",
        step={"id": step_id},
    )
    return DataChunk(
        type="data-strategy-update",
        data=payload.model_dump(by_alias=True, mode="json"),
    )


def strategy_meta_chunk(graph: StrategyGraph) -> DataChunk:
    """Build the ``data-strategy-meta`` DataChunk for a graph's metadata."""
    sync_state = getattr(graph, "sync_state", None)
    total_size = 0
    if sync_state is not None:
        for root_id in graph.roots:
            count = sync_state.step_counts.get(root_id)
            if isinstance(count, int):
                total_size += count
    payload = StrategyMeta(
        strategy_id=graph.id,
        name=graph.name,
        is_saved=False,
        estimated_size=total_size,
        record_class_name=graph.record_type or "transcript",
    )
    return DataChunk(
        type="data-strategy-meta",
        data=payload.model_dump(by_alias=True, mode="json"),
    )


def strategy_link_chunk(
    *,
    strategy_id: str,
    url: str,
    title: str | None = None,
) -> DataChunk:
    """Build the ``data-strategy-link`` DataChunk.

    Pydantic validates ``url`` starts with ``http://`` or ``https://``.
    """
    payload = StrategyLink(strategy_id=strategy_id, url=url, title=title)
    return DataChunk(
        type="data-strategy-link",
        data=payload.model_dump(by_alias=True, mode="json"),
    )


# ── Problem frame ──────────────────────────────────────────────────────────


def problem_frame_chunk(
    frame: ProblemFrame, *, site_id: str
) -> DataChunk:
    """Build the ``data-problem-frame`` DataChunk from an internal ProblemFrame."""
    intent = frame.interpreted_goal or frame.user_goal
    payload = ProblemFramePart(
        intent_summary=intent,
        entities=list(frame.biological_entities),
        site_id=site_id,
    )
    return DataChunk(
        type="data-problem-frame",
        data=payload.model_dump(by_alias=True, mode="json"),
    )


# ── Plan / decision ────────────────────────────────────────────────────────


class _SimplePlanStep(CamelModel):
    """Minimal shape used to derive plan-artifact steps without pulling domain deps."""

    search_name: str
    rationale: str = ""


def plan_artifact_chunk(
    *,
    plan_id: str,
    steps: list[PlannedStep],
    rationale: str,
) -> DataChunk:
    """Build the ``data-plan-artifact`` DataChunk for a proposed plan."""
    payload = PlanArtifact(
        plan_id=plan_id,
        steps=steps,
        rationale=rationale,
    )
    return DataChunk(
        type="data-plan-artifact",
        data=payload.model_dump(by_alias=True, mode="json"),
    )


def decision_presented_chunk(
    *,
    decision_type: str,
    options: list[dict[str, object]],
    rationale: str | None = None,
) -> DataChunk:
    """Build the ``data-decision-presented`` DataChunk for a branching decision."""
    payload = DecisionPresented(
        decision_type=decision_type,
        options=options,
        rationale=rationale,
    )
    return DataChunk(
        type="data-decision-presented",
        data=payload.model_dump(by_alias=True, mode="json"),
    )


# ── Gene set ───────────────────────────────────────────────────────────────


def gene_set_chunk(
    *,
    gene_set_id: str,
    name: str,
    gene_count: int,
    site_id: str,
) -> DataChunk:
    """Build the ``data-gene-set`` DataChunk for a workbench gene set."""
    payload = GeneSetPart(
        gene_set_id=gene_set_id,
        name=name,
        gene_count=gene_count,
        site_id=site_id,
    )
    return DataChunk(
        type="data-gene-set",
        data=payload.model_dump(by_alias=True, mode="json"),
    )


# ── Conversation title ─────────────────────────────────────────────────────


def conversation_title_chunk(title: str) -> DataChunk:
    """Build the ``data-conversation-title`` DataChunk."""
    payload = ConversationTitle(title=title)
    return DataChunk(
        type="data-conversation-title",
        data=payload.model_dump(by_alias=True, mode="json"),
    )


# ── Source URLs (citations) ────────────────────────────────────────────────


def source_url_chunks_from_citations(
    citations: list[object],
) -> list[SourceUrlChunk]:
    """Emit one ``SourceUrlChunk`` per citation with a URL.

    The citation type is kept loose here so any object with ``id``, ``url``,
    and ``title`` attributes works — the research domain's ``Citation``
    model and similar shapes. Citations without a URL are skipped because
    ``SourceUrlChunk.url`` is required.
    """
    chunks: list[SourceUrlChunk] = []
    for cit in citations:
        url = getattr(cit, "url", None)
        if not isinstance(url, str) or not url:
            continue
        cit_id = getattr(cit, "id", "")
        title = getattr(cit, "title", None)
        chunks.append(
            SourceUrlChunk(
                source_id=str(cit_id) or url,
                url=url,
                title=title if isinstance(title, str) else None,
            )
        )
    return chunks

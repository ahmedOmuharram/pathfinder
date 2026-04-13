"""Typed payloads for graph/strategy data-parts."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from shared_py.pydantic_base import CamelModel


# Matches WDK BooleanOperator (canonical 7) and the frontend `CombineOperator`
# union in `packages/shared-ts/src/types.ts`. Narrowing to a subset would silently
# drop valid WDK operators in graph snapshots.
GraphEdgeOperator = Literal[
    "INTERSECT", "UNION", "MINUS", "RMINUS", "LONLY", "RONLY", "COLOCATE"
]


class GraphNode(CamelModel):
    id: str
    search_name: str
    estimated_size: int = Field(ge=0)


class GraphEdge(CamelModel):
    source: str
    target: str
    operator: GraphEdgeOperator | None = None


class GraphSnapshot(CamelModel):
    strategy_id: str
    gene_count: int = Field(ge=0)
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class GraphPlan(CamelModel):
    """A planned (not-yet-applied) strategy graph."""

    nodes: list[GraphNode]
    edges: list[GraphEdge]
    rationale: str | None = None


class GraphCleared(CamelModel):
    """Sentinel indicating the strategy graph was cleared."""

    reason: str | None = None

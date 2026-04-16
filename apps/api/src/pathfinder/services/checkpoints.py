from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langgraph.types import StateSnapshot
from pydantic import Field, TypeAdapter
from sqlalchemy import text
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.platform.pydantic_base import CamelModel


class GraphLike(Protocol):
    """Subset of ``CompiledStateGraph`` the service actually depends on.

    Decoupling here keeps the service usable with both the production
    ``PipelineState`` graph and lightweight test graphs (TypedDict state)
    without parameterizing every caller through generics.
    """

    async def aget_state(
        self, config: RunnableConfig, **kwargs: Any
    ) -> StateSnapshot: ...

    async def aupdate_state(
        self,
        config: RunnableConfig,
        values: dict[str, Any] | Any,
        as_node: str | None = None,
    ) -> RunnableConfig: ...


SessionFactory = Callable[[], AsyncSession]
GraphFactory = Callable[[], GraphLike]


class CheckpointNode(CamelModel):
    """Tree node returned by ``CheckpointService.list_tree``.

    Built from a single row of the LangGraph ``checkpoints`` table joined
    with the per-user ``checkpoint_labels`` sidecar. ``node`` is derived
    from the parent checkpoint's ``branch:to:<node>`` write — that is
    LangGraph's own routing channel and so identifies the node that
    produced this checkpoint. ``source`` is one of ``input``/``loop``/
    ``update``/``fork`` (LangGraph's own classification).
    """

    checkpoint_id: str
    parent_checkpoint_id: str | None
    thread_id: str
    source: str
    step: int
    node: str | None
    created_at: str
    label: str | None = None
    pinned: bool = False


class CheckpointSnapshot(CamelModel):
    """Full materialized checkpoint state from ``graph.aget_state``."""

    checkpoint_id: str
    thread_id: str
    values: dict[str, Any] = Field(default_factory=dict)
    next: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    parent_checkpoint_id: str | None = None


class _LabelEntry(CamelModel):
    label: str | None
    pinned: bool


class _ForkedConfigurable(CamelModel):
    """Strict view of the ``configurable`` dict returned from a fork.

    LangGraph populates ``checkpoint_id`` synchronously after
    ``aupdate_state`` succeeds; if it ever shipped without it, validation
    fails fast here rather than 500-ing later.
    """

    checkpoint_id: str


@dataclass
class CheckpointService:
    """Tree + fork operations on top of the LangGraph checkpoint store.

    ``list_tree`` reads only the shape (parent links, metadata) via direct
    SQL on the ``checkpoints`` table, deliberately avoiding the JSONB blob
    deserialization the Saver's ``alist`` would force. ``get_snapshot``
    falls back to the Saver path when callers actually want the values.
    ``fork`` delegates to ``graph.aupdate_state``, which writes a new
    checkpoint whose ``parent_checkpoint_id`` is the source.
    """

    session_factory: SessionFactory
    graph_factory: GraphFactory

    async def list_tree(
        self,
        *,
        thread_id: str,
        user_id: UUID | None = None,
    ) -> list[CheckpointNode]:
        async with self.session_factory() as session:
            checkpoint_rows = await self._fetch_checkpoint_rows(
                session, thread_id=thread_id
            )
            label_map = await self._fetch_label_map(
                session, thread_id=thread_id, user_id=user_id
            )
        return [
            _row_to_node(row, thread_id=thread_id, label_map=label_map)
            for row in checkpoint_rows
        ]

    async def get_snapshot(
        self, *, thread_id: str, checkpoint_id: str
    ) -> CheckpointSnapshot:
        graph = self.graph_factory()
        config: RunnableConfig = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_id,
            }
        }
        snapshot: StateSnapshot = await graph.aget_state(config)
        return _snapshot_to_model(
            snapshot,
            thread_id=thread_id,
            checkpoint_id=checkpoint_id,
        )

    async def fork(
        self,
        *,
        thread_id: str,
        from_checkpoint_id: str,
        state_override: dict[str, Any] | None = None,
        as_node: str | None = None,
    ) -> str:
        graph = self.graph_factory()
        parent_config: RunnableConfig = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_id": from_checkpoint_id,
            }
        }
        new_config = await graph.aupdate_state(
            parent_config,
            state_override or {},
            as_node=as_node,
        )
        configurable = _ForkedConfigurable.model_validate(
            new_config.get("configurable") or {}
        )
        return configurable.checkpoint_id

    async def _fetch_checkpoint_rows(
        self, session: AsyncSession, *, thread_id: str
    ) -> list[Row[Any]]:
        # The "node that produced this checkpoint" is derived from the parent
        # checkpoint's `branch:to:<node>` write — that is literally how
        # LangGraph routes which node fires after a checkpoint. The
        # subquery's LIMIT 1 collapses parallel-edge rows into a single name.
        result = await session.execute(
            text(
                "SELECT c.checkpoint_id, c.parent_checkpoint_id, c.metadata, "
                "c.checkpoint->>'ts' AS created_at, "
                "(SELECT substring(cw.channel FROM 'branch:to:(.*)') "
                "   FROM checkpoint_writes cw "
                "   WHERE cw.thread_id = c.thread_id "
                "     AND cw.checkpoint_ns = c.checkpoint_ns "
                "     AND cw.checkpoint_id = c.parent_checkpoint_id "
                "     AND cw.channel LIKE 'branch:to:%' "
                "   LIMIT 1) AS node_name "
                "FROM checkpoints c "
                "WHERE c.thread_id = :thread_id AND c.checkpoint_ns = '' "
                "ORDER BY (c.metadata->>'step')::int ASC NULLS LAST, "
                "c.checkpoint_id ASC"
            ),
            {"thread_id": thread_id},
        )
        return list(result.fetchall())

    async def _fetch_label_map(
        self,
        session: AsyncSession,
        *,
        thread_id: str,
        user_id: UUID | None,
    ) -> dict[str, _LabelEntry]:
        if user_id is None:
            return {}
        result = await session.execute(
            text(
                "SELECT checkpoint_id, label, pinned "
                "FROM checkpoint_labels "
                "WHERE thread_id = :thread_id AND user_id = :user_id"
            ),
            {"thread_id": thread_id, "user_id": user_id},
        )
        return {
            row.checkpoint_id: _LabelEntry(label=row.label, pinned=row.pinned)
            for row in result.fetchall()
        }


class _RawMetadata(CamelModel):
    """Coerce ``checkpoints.metadata`` JSONB into typed shape.

    The Pregel loop populates ``source`` and ``step`` on every checkpoint
    it writes; both default-fill so a row with empty metadata does not
    crash the listing.
    """

    source: str = "loop"
    step: int = 0


def _row_to_node(
    row: Row[Any],
    *,
    thread_id: str,
    label_map: dict[str, _LabelEntry],
) -> CheckpointNode:
    metadata = _RawMetadata.model_validate(row.metadata or {})
    label_entry = label_map.get(row.checkpoint_id)
    return CheckpointNode(
        checkpoint_id=row.checkpoint_id,
        parent_checkpoint_id=row.parent_checkpoint_id,
        thread_id=thread_id,
        source=metadata.source,
        step=metadata.step,
        node=row.node_name,
        created_at=row.created_at or "",
        label=label_entry.label if label_entry else None,
        pinned=label_entry.pinned if label_entry else False,
    )


_VALUES_ADAPTER: TypeAdapter[dict[str, Any]] = TypeAdapter(dict[str, Any])
_METADATA_ADAPTER: TypeAdapter[dict[str, Any]] = TypeAdapter(dict[str, Any])


class _ParentConfig(CamelModel):
    checkpoint_id: str | None = None


def _snapshot_to_model(
    snapshot: StateSnapshot,
    *,
    thread_id: str,
    checkpoint_id: str,
) -> CheckpointSnapshot:
    parent_cp_id: str | None = None
    if snapshot.parent_config is not None:
        configurable = snapshot.parent_config.get("configurable") or {}
        parent = _ParentConfig.model_validate(configurable)
        parent_cp_id = parent.checkpoint_id

    created_at = snapshot.created_at or ""
    metadata_dict: dict[str, Any] = _METADATA_ADAPTER.validate_python(
        snapshot.metadata or {}
    )
    values_dict: dict[str, Any] = _VALUES_ADAPTER.validate_python(
        snapshot.values or {}
    )
    return CheckpointSnapshot(
        checkpoint_id=checkpoint_id,
        thread_id=thread_id,
        values=values_dict,
        next=list(snapshot.next),
        metadata=metadata_dict,
        created_at=created_at,
        parent_checkpoint_id=parent_cp_id,
    )

"""Repository for stream (conversation) identity + projections."""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from shared_py.defaults import DEFAULT_STREAM_NAME
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from veupath_chatbot.persistence.models import Operation, Stream, StreamProjection
from veupath_chatbot.platform.types import JSONObject


@dataclass
class ProjectionUpdate:
    """Partial update payload for a StreamProjection.

    Only fields explicitly set to non-None (or flagged with ``*_set=True``)
    are written. Use ``wdk_strategy_id_set=True`` to explicitly set that
    field (even to ``None``), similarly for ``is_saved_set``,
    ``estimated_size_set``, ``gene_set_id_set``.
    """

    name: str | None = None
    record_type: str | None = None
    wdk_strategy_id: int | None = None
    wdk_strategy_id_set: bool = False
    is_saved: bool | None = None
    is_saved_set: bool = False
    plan: JSONObject | None = None
    step_count: int | None = None
    estimated_size: int | None = None
    estimated_size_set: bool = False
    gene_set_id: str | None = None
    gene_set_id_set: bool = False
    gene_set_auto_imported: bool | None = None
    model_id: str | None = field(default=None)


class StreamRepository:
    """Data access for conversation streams and their projections."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── Helpers ──

    async def _deduplicate_name(
        self,
        user_id: UUID,
        site_id: str,
        name: str,
        exclude_stream_id: UUID | None = None,
    ) -> str:
        """Return a unique name for a projection within (user, site).

        If ``name`` already exists, appends ``(1)``, ``(2)``, etc.
        """
        query = (
            select(StreamProjection.name)
            .join(Stream)
            .where(Stream.user_id == user_id, Stream.site_id == site_id)
        )
        if exclude_stream_id is not None:
            query = query.where(StreamProjection.stream_id != exclude_stream_id)
        result = await self.session.execute(query)
        existing: set[str] = {row[0] for row in result.all() if row[0]}

        if name not in existing:
            return name

        i = 1
        while f"{name} ({i})" in existing:
            i += 1
        return f"{name} ({i})"

    # ── Identity ──

    async def create(
        self,
        user_id: UUID,
        site_id: str,
        *,
        stream_id: UUID | None = None,
        name: str = "",
        experiment_id: str | None = None,
    ) -> Stream:
        resolved_name = await self._deduplicate_name(
            user_id,
            site_id,
            name or DEFAULT_STREAM_NAME,
        )
        stream = Stream(
            id=stream_id or uuid4(),
            user_id=user_id,
            site_id=site_id,
            experiment_id=experiment_id,
        )
        self.session.add(stream)
        await self.session.flush()

        proj = StreamProjection(
            stream_id=stream.id,
            name=resolved_name,
            site_id=site_id,
        )
        self.session.add(proj)
        await self.session.flush()

        return stream

    async def get_by_id(self, stream_id: UUID) -> Stream | None:
        result = await self.session.execute(
            select(Stream).where(Stream.id == stream_id)
        )
        return result.scalar_one_or_none()

    async def find_by_experiment(
        self, user_id: UUID, experiment_id: str
    ) -> Stream | None:
        """Find an existing stream for a user + experiment combination."""
        result = await self.session.execute(
            select(Stream).where(
                Stream.user_id == user_id,
                Stream.experiment_id == experiment_id,
            )
        )
        return result.scalar_one_or_none()

    async def delete(self, stream_id: UUID) -> None:
        await self.session.execute(delete(Stream).where(Stream.id == stream_id))

    # ── Projections ──

    async def get_projection(self, stream_id: UUID) -> StreamProjection | None:
        result = await self.session.execute(
            select(StreamProjection)
            .options(joinedload(StreamProjection.stream))
            .where(StreamProjection.stream_id == stream_id)
        )
        return result.scalar_one_or_none()

    async def list_projections(
        self,
        user_id: UUID,
        site_id: str | None = None,
        limit: int = 50,
    ) -> list[StreamProjection]:
        stmt = (
            select(StreamProjection)
            .join(Stream)
            .options(joinedload(StreamProjection.stream))
            .where(Stream.user_id == user_id)
            .where(StreamProjection.dismissed_at.is_(None))
            .order_by(StreamProjection.updated_at.desc())
            .limit(limit)
        )
        if site_id:
            stmt = stmt.where(Stream.site_id == site_id)
        result = await self.session.execute(stmt)
        return list(result.unique().scalars().all())

    async def get_by_wdk_strategy_id(
        self, user_id: UUID, wdk_strategy_id: int
    ) -> StreamProjection | None:
        result = await self.session.execute(
            select(StreamProjection)
            .join(Stream)
            .options(joinedload(StreamProjection.stream))
            .where(
                Stream.user_id == user_id,
                StreamProjection.wdk_strategy_id == wdk_strategy_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_projection(self, stream_id: UUID, upd: ProjectionUpdate) -> None:
        """Dynamically update a StreamProjection based on provided fields.

        Steps and root_step_id are derived from plan at read time; only plan
        and a denormalized step_count are persisted on write.
        """
        values: dict[str, Any] = {"updated_at": datetime.now(UTC)}
        if upd.name is not None:
            # Deduplicate rename against other projections for the same user+site.
            proj = await self.get_projection(stream_id)
            if proj and proj.stream:
                upd.name = await self._deduplicate_name(
                    proj.stream.user_id,
                    proj.stream.site_id,
                    upd.name,
                    exclude_stream_id=stream_id,
                )
            values["name"] = upd.name
        if upd.record_type is not None:
            values["record_type"] = upd.record_type
        if upd.wdk_strategy_id_set:
            values["wdk_strategy_id"] = upd.wdk_strategy_id
        if upd.is_saved_set:
            values["is_saved"] = bool(upd.is_saved)
        if upd.plan is not None:
            values["plan"] = upd.plan
        if upd.step_count is not None:
            values["step_count"] = upd.step_count
        if upd.estimated_size_set:
            values["estimated_size"] = upd.estimated_size
        if upd.gene_set_id_set:
            values["gene_set_id"] = upd.gene_set_id
        if upd.gene_set_auto_imported is not None:
            values["gene_set_auto_imported"] = upd.gene_set_auto_imported
        if upd.model_id is not None:
            values["model_id"] = upd.model_id

        await self.session.execute(
            update(StreamProjection)
            .where(StreamProjection.stream_id == stream_id)
            .values(**values)
        )
        await self.session.flush()

    async def dismiss(self, stream_id: UUID) -> None:
        """Soft-delete: mark a projection as dismissed (hidden from main list)."""
        await self.session.execute(
            update(StreamProjection)
            .where(StreamProjection.stream_id == stream_id)
            .values(dismissed_at=datetime.now(UTC))
        )
        await self.session.flush()

    async def restore(self, stream_id: UUID) -> None:
        """Un-dismiss: restore a dismissed projection and reset for fresh WDK import."""
        await self.session.execute(
            update(StreamProjection)
            .where(StreamProjection.stream_id == stream_id)
            .values(
                dismissed_at=None,
                plan={},
                message_count=0,
            )
        )
        await self.session.flush()

    async def list_dismissed_projections(
        self,
        user_id: UUID,
        site_id: str | None = None,
        limit: int = 50,
    ) -> list[StreamProjection]:
        stmt = (
            select(StreamProjection)
            .join(Stream)
            .options(joinedload(StreamProjection.stream))
            .where(Stream.user_id == user_id)
            .where(StreamProjection.dismissed_at.isnot(None))
            .order_by(StreamProjection.dismissed_at.desc())
            .limit(limit)
        )
        if site_id:
            stmt = stmt.where(Stream.site_id == site_id)
        result = await self.session.execute(stmt)
        return list(result.unique().scalars().all())

    async def prune_wdk_orphans(
        self,
        user_id: UUID,
        site_id: str,
        live_wdk_ids: set[int],
    ) -> int:
        """Delete streams whose projections have wdk_strategy_id not in the live set.

        Returns the number of pruned streams.
        """
        # Single query: fetch projections with wdk links, filtering in SQL.
        stmt = (
            select(StreamProjection.stream_id, StreamProjection.wdk_strategy_id)
            .join(Stream)
            .where(
                Stream.user_id == user_id,
                Stream.site_id == site_id,
                StreamProjection.wdk_strategy_id.isnot(None),
                StreamProjection.dismissed_at.is_(None),
            )
        )
        result = await self.session.execute(stmt)
        rows = result.all()

        # Filter to orphans whose wdk_strategy_id is not in the live set.
        orphan_ids = [
            stream_id for stream_id, wdk_id in rows if wdk_id not in live_wdk_ids
        ]

        if not orphan_ids:
            return 0

        # Batch delete all orphan streams (cascade deletes projections).
        await self.session.execute(delete(Stream).where(Stream.id.in_(orphan_ids)))
        await self.session.flush()
        return len(orphan_ids)

    # ── Operations ──

    async def register_operation(
        self, operation_id: str, stream_id: UUID, op_type: str
    ) -> Operation:
        op = Operation(
            operation_id=operation_id,
            stream_id=stream_id,
            type=op_type,
            status="active",
        )
        self.session.add(op)
        await self.session.flush()
        return op

    async def _set_operation_status(self, operation_id: str, status: str) -> None:
        await self.session.execute(
            update(Operation)
            .where(Operation.operation_id == operation_id)
            .values(status=status, completed_at=datetime.now(UTC))
        )
        await self.session.flush()

    async def complete_operation(self, operation_id: str) -> None:
        await self._set_operation_status(operation_id, "completed")

    async def fail_operation(self, operation_id: str) -> None:
        await self._set_operation_status(operation_id, "failed")

    async def cancel_operation(self, operation_id: str) -> None:
        await self._set_operation_status(operation_id, "cancelled")

    async def get_active_operations(self, stream_id: UUID) -> list[Operation]:
        result = await self.session.execute(
            select(Operation)
            .where(Operation.stream_id == stream_id, Operation.status == "active")
            .order_by(Operation.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_active_operations(
        self, op_type: str | None = None
    ) -> list[Operation]:
        stmt = select(Operation).where(Operation.status == "active")
        if op_type:
            stmt = stmt.where(Operation.type == op_type)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def expire_stale_operations(self, max_age_seconds: int = 600) -> int:
        """Mark operations active longer than *max_age_seconds* as failed.

        Returns the number of expired operations.
        """
        cutoff = datetime.now(UTC) - timedelta(seconds=max_age_seconds)
        result = await self.session.execute(
            update(Operation)
            .where(Operation.status == "active", Operation.created_at < cutoff)
            .values(status="failed", completed_at=datetime.now(UTC))
        )
        await self.session.flush()
        return result.rowcount

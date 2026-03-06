"""Gene set store with write-through DB persistence.

Keeps an in-memory dict for fast synchronous access during AI tool calls,
and persists every mutation to PostgreSQL so gene sets survive API restarts.
Follows the same pattern as ExperimentStore.
"""

from __future__ import annotations

from datetime import UTC, datetime
from functools import cache
from uuid import UUID

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from veupath_chatbot.persistence.models import GeneSetRow
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.tasks import spawn
from veupath_chatbot.services.gene_sets.types import GeneSet

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Private DB helpers
# ---------------------------------------------------------------------------


def _row_from_gene_set(gs: GeneSet) -> dict[str, object]:
    return {
        "id": gs.id,
        "user_id": str(gs.user_id) if gs.user_id else None,
        "site_id": gs.site_id,
        "name": gs.name,
        "gene_ids": gs.gene_ids,
        "source": gs.source,
        "wdk_strategy_id": gs.wdk_strategy_id,
        "wdk_step_id": gs.wdk_step_id,
        "search_name": gs.search_name,
        "record_type": gs.record_type,
        "parameters": gs.parameters,
        "parent_set_ids": gs.parent_set_ids,
        "operation": gs.operation,
        "step_count": gs.step_count,
        "created_at": gs.created_at,
    }


def _gene_set_from_row(row: GeneSetRow) -> GeneSet:
    return GeneSet(
        id=row.id,
        user_id=UUID(row.user_id) if row.user_id else None,
        site_id=row.site_id,
        name=row.name,
        gene_ids=row.gene_ids or [],
        source=row.source,
        created_at=row.created_at or datetime.now(UTC),
        wdk_strategy_id=row.wdk_strategy_id,
        wdk_step_id=row.wdk_step_id,
        search_name=row.search_name,
        record_type=row.record_type,
        parameters=row.parameters,
        parent_set_ids=row.parent_set_ids or [],
        operation=row.operation,
        step_count=row.step_count or 1,
    )


async def _persist_to_db(gs: GeneSet) -> None:
    from veupath_chatbot.persistence.session import async_session_factory

    try:
        vals = _row_from_gene_set(gs)
        stmt = (
            pg_insert(GeneSetRow)
            .values(**vals)
            .on_conflict_do_update(
                index_elements=[GeneSetRow.id],
                set_={k: v for k, v in vals.items() if k != "id"},
            )
        )
        async with async_session_factory() as session:
            await session.execute(stmt)
            await session.commit()
    except Exception:
        logger.exception("Failed to persist gene set to DB", gene_set_id=gs.id)


async def _load_from_db(gene_set_id: str) -> GeneSet | None:
    from veupath_chatbot.persistence.session import async_session_factory

    async with async_session_factory() as session:
        row = await session.get(GeneSetRow, gene_set_id)
        if row is None:
            return None
        return _gene_set_from_row(row)


async def _list_from_db(
    user_id: str | None = None,
    site_id: str | None = None,
) -> list[GeneSet]:
    from veupath_chatbot.persistence.session import async_session_factory

    stmt = select(GeneSetRow)
    if user_id:
        stmt = stmt.where(GeneSetRow.user_id == user_id)
    if site_id:
        stmt = stmt.where(GeneSetRow.site_id == site_id)
    stmt = stmt.order_by(GeneSetRow.created_at.desc())

    async with async_session_factory() as session:
        result = await session.execute(stmt)
        rows = result.scalars().all()
        return [_gene_set_from_row(r) for r in rows]


async def _delete_from_db(gene_set_id: str) -> None:
    from veupath_chatbot.persistence.session import async_session_factory

    stmt = sa_delete(GeneSetRow).where(GeneSetRow.id == gene_set_id)
    async with async_session_factory() as session:
        await session.execute(stmt)
        await session.commit()


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


class GeneSetStore:
    """Gene set repository with in-memory cache and DB write-through.

    Sync methods are safe for asyncio cooperative multitasking: all dict
    operations complete without yielding.  DB writes are scheduled as
    fire-and-forget tasks so callers never block.
    """

    def __init__(self) -> None:
        self._sets: dict[str, GeneSet] = {}

    # -- Sync interface (used by AI tools / workbench_tools.py) ----------------

    def save(self, gene_set: GeneSet) -> None:
        self._sets[gene_set.id] = gene_set
        coro = _persist_to_db(gene_set)
        try:
            spawn(coro, name=f"persist-gs-{gene_set.id}")
        except RuntimeError:
            coro.close()
            logger.warning("No event loop for DB persist", gene_set_id=gene_set.id)

    def get(self, gene_set_id: str) -> GeneSet | None:
        return self._sets.get(gene_set_id)

    def list_all(self, *, site_id: str | None = None) -> list[GeneSet]:
        results = list(self._sets.values())
        if site_id is not None:
            results = [gs for gs in results if gs.site_id == site_id]
        return sorted(results, key=lambda gs: gs.created_at, reverse=True)

    def list_for_user(
        self,
        user_id: UUID,
        *,
        site_id: str | None = None,
    ) -> list[GeneSet]:
        results = [gs for gs in self._sets.values() if gs.user_id == user_id]
        if site_id is not None:
            results = [gs for gs in results if gs.site_id == site_id]
        return sorted(results, key=lambda gs: gs.created_at, reverse=True)

    def delete(self, gene_set_id: str) -> bool:
        removed = gene_set_id in self._sets
        self._sets.pop(gene_set_id, None)
        coro = _delete_from_db(gene_set_id)
        try:
            spawn(coro, name=f"delete-gs-{gene_set_id}")
        except RuntimeError:
            coro.close()
            logger.warning("No event loop for DB delete", gene_set_id=gene_set_id)
        return removed

    # -- Async interface (used by endpoint handlers) ---------------------------

    async def aget(self, gene_set_id: str) -> GeneSet | None:
        gs = self._sets.get(gene_set_id)
        if gs is not None:
            return gs
        gs = await _load_from_db(gene_set_id)
        if gs is not None:
            self._sets[gene_set_id] = gs
        return gs

    async def alist_for_user(
        self,
        user_id: UUID,
        *,
        site_id: str | None = None,
    ) -> list[GeneSet]:
        db_sets = await _list_from_db(user_id=str(user_id), site_id=site_id)
        merged: dict[str, GeneSet] = {gs.id: gs for gs in db_sets}
        for gid, gs in self._sets.items():
            if gs.user_id != user_id:
                continue
            if site_id and gs.site_id != site_id:
                continue
            merged[gid] = gs
        result = list(merged.values())
        result.sort(key=lambda gs: gs.created_at, reverse=True)
        return result

    async def adelete(self, gene_set_id: str) -> bool:
        self._sets.pop(gene_set_id, None)
        await _delete_from_db(gene_set_id)
        return True


@cache
def get_gene_set_store() -> GeneSetStore:
    """Get the global gene set store singleton."""
    return GeneSetStore()

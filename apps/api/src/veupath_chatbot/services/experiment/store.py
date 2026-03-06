"""Experiment store with write-through DB persistence.

Provides CRUD operations for experiment lifecycle management.
Keeps an in-memory dict for fast synchronous access during experiment
execution, and persists every mutation to PostgreSQL so experiments
survive API restarts.
"""

from __future__ import annotations

from datetime import UTC, datetime
from functools import cache

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from veupath_chatbot.persistence.models import ExperimentRow
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.tasks import spawn
from veupath_chatbot.services.experiment._deserialize import experiment_from_json
from veupath_chatbot.services.experiment.types import (
    Experiment,
    experiment_to_json,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Private DB helpers (use async_session_factory directly)
# ---------------------------------------------------------------------------


def _parse_created_at(iso_str: str) -> datetime:
    """Parse an ISO datetime string to a timezone-aware datetime."""
    if not iso_str:
        return datetime.now(UTC)
    dt = datetime.fromisoformat(iso_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _row_from_experiment(exp: Experiment) -> dict[str, object]:
    """Build column values for an ExperimentRow upsert."""
    return {
        "id": exp.id,
        "site_id": exp.config.site_id,
        "user_id": exp.user_id,
        "name": exp.config.name or "",
        "status": exp.status,
        "data": experiment_to_json(exp),
        "batch_id": exp.batch_id,
        "benchmark_id": exp.benchmark_id,
        "created_at": _parse_created_at(exp.created_at),
    }


async def _persist_to_db(exp: Experiment) -> None:
    """Upsert an experiment row into the database."""
    from veupath_chatbot.persistence.session import async_session_factory

    try:
        vals = _row_from_experiment(exp)
        stmt = (
            pg_insert(ExperimentRow)
            .values(**vals)
            .on_conflict_do_update(
                index_elements=[ExperimentRow.id],
                set_={k: v for k, v in vals.items() if k != "id"},
            )
        )
        async with async_session_factory() as session:
            await session.execute(stmt)
            await session.commit()
    except Exception:
        logger.exception("Failed to persist experiment to DB", experiment_id=exp.id)


async def _load_from_db(experiment_id: str) -> Experiment | None:
    """Load a single experiment from the database."""
    from veupath_chatbot.persistence.session import async_session_factory

    async with async_session_factory() as session:
        row = await session.get(ExperimentRow, experiment_id)
        if row is None:
            return None
        return experiment_from_json(row.data)


async def _list_from_db(
    site_id: str | None = None,
    user_id: str | None = None,
) -> list[Experiment]:
    """List experiments from the database, optionally filtered by site and user."""
    from veupath_chatbot.persistence.session import async_session_factory

    stmt = select(ExperimentRow)
    if site_id:
        stmt = stmt.where(ExperimentRow.site_id == site_id)
    if user_id:
        stmt = stmt.where(ExperimentRow.user_id == user_id)
    stmt = stmt.order_by(ExperimentRow.created_at.desc())

    async with async_session_factory() as session:
        result = await session.execute(stmt)
        rows = result.scalars().all()
        return [experiment_from_json(r.data) for r in rows]


async def _list_by_benchmark_from_db(benchmark_id: str) -> list[Experiment]:
    """List experiments from the database by benchmark_id."""
    from veupath_chatbot.persistence.session import async_session_factory

    stmt = select(ExperimentRow).where(ExperimentRow.benchmark_id == benchmark_id)
    async with async_session_factory() as session:
        result = await session.execute(stmt)
        rows = result.scalars().all()
        return [experiment_from_json(r.data) for r in rows]


async def _delete_from_db(experiment_id: str) -> None:
    """Delete an experiment row from the database."""
    from veupath_chatbot.persistence.session import async_session_factory

    stmt = sa_delete(ExperimentRow).where(ExperimentRow.id == experiment_id)
    async with async_session_factory() as session:
        await session.execute(stmt)
        await session.commit()


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


class ExperimentStore:
    """Experiment repository with in-memory cache and DB write-through.

    Sync methods are safe for asyncio cooperative multitasking: all dict
    operations complete without yielding.  DB writes are scheduled as
    fire-and-forget tasks so callers never block.
    """

    def __init__(self) -> None:
        self._experiments: dict[str, Experiment] = {}

    # -- Sync interface (used by service.py / ai_analysis_tools.py) ----------

    def save(self, experiment: Experiment) -> None:
        """Create or update an experiment (in-memory + schedule DB write)."""
        self._experiments[experiment.id] = experiment
        coro = _persist_to_db(experiment)
        try:
            spawn(coro, name=f"persist-exp-{experiment.id}")
        except RuntimeError:
            coro.close()
            logger.warning("No event loop for DB persist", experiment_id=experiment.id)

    def get(self, experiment_id: str) -> Experiment | None:
        """Get an experiment by ID from in-memory cache."""
        return self._experiments.get(experiment_id)

    def list_all(
        self, site_id: str | None = None, user_id: str | None = None
    ) -> list[Experiment]:
        """List experiments from in-memory cache."""
        experiments = list(self._experiments.values())
        if site_id:
            experiments = [e for e in experiments if e.config.site_id == site_id]
        if user_id:
            experiments = [e for e in experiments if e.user_id == user_id]
        experiments.sort(key=lambda e: e.created_at, reverse=True)
        return experiments

    def list_by_benchmark(self, benchmark_id: str) -> list[Experiment]:
        """Return all experiments belonging to a benchmark suite (in-memory)."""
        exps = [e for e in self._experiments.values() if e.benchmark_id == benchmark_id]
        exps.sort(key=lambda e: (not e.is_primary_benchmark, e.created_at))
        return exps

    def delete(self, experiment_id: str) -> bool:
        """Delete from in-memory + schedule DB delete."""
        removed = experiment_id in self._experiments
        self._experiments.pop(experiment_id, None)
        coro = _delete_from_db(experiment_id)
        try:
            spawn(coro, name=f"delete-exp-{experiment_id}")
        except RuntimeError:
            coro.close()
            logger.warning("No event loop for DB delete", experiment_id=experiment_id)
        return removed

    # -- Async interface (used by endpoint handlers) -------------------------

    async def aget(self, experiment_id: str) -> Experiment | None:
        """Get an experiment: in-memory first, then DB fallback."""
        exp = self._experiments.get(experiment_id)
        if exp is not None:
            return exp
        exp = await _load_from_db(experiment_id)
        if exp is not None:
            self._experiments[experiment_id] = exp
        return exp

    async def alist_all(
        self, site_id: str | None = None, user_id: str | None = None
    ) -> list[Experiment]:
        """List experiments: merges DB rows with in-memory (fresher) state."""
        db_exps = await _list_from_db(site_id, user_id)
        merged: dict[str, Experiment] = {e.id: e for e in db_exps}
        # In-memory entries override DB (running experiments have fresher state)
        for eid, exp in self._experiments.items():
            if site_id and exp.config.site_id != site_id:
                continue
            if user_id and exp.user_id != user_id:
                continue
            merged[eid] = exp
        result = list(merged.values())
        result.sort(key=lambda e: e.created_at, reverse=True)
        return result

    async def alist_by_benchmark(self, benchmark_id: str) -> list[Experiment]:
        """List experiments by benchmark: merges DB + in-memory."""
        db_exps = await _list_by_benchmark_from_db(benchmark_id)
        merged: dict[str, Experiment] = {e.id: e for e in db_exps}
        for eid, exp in self._experiments.items():
            if exp.benchmark_id == benchmark_id:
                merged[eid] = exp
        result = list(merged.values())
        result.sort(key=lambda e: (not e.is_primary_benchmark, e.created_at))
        return result

    async def adelete(self, experiment_id: str) -> bool:
        """Delete from both in-memory and DB."""
        self._experiments.pop(experiment_id, None)
        await _delete_from_db(experiment_id)
        return True


@cache
def get_experiment_store() -> ExperimentStore:
    """Get the global experiment store singleton."""
    return ExperimentStore()

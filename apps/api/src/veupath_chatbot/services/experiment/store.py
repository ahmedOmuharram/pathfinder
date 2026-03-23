"""Experiment store with write-through DB persistence.

Provides CRUD operations for experiment lifecycle management.
Keeps an in-memory dict for fast synchronous access during experiment
execution, and persists every mutation to PostgreSQL so experiments
survive API restarts.
"""

from datetime import UTC, datetime
from functools import cache

from sqlalchemy import select

from veupath_chatbot.persistence.models import ExperimentRow
from veupath_chatbot.persistence.session import async_session_factory
from veupath_chatbot.platform.store import WriteThruStore
from veupath_chatbot.services.experiment._deserialize import experiment_from_json
from veupath_chatbot.services.experiment.types import (
    Experiment,
    experiment_to_json,
)

# ---------------------------------------------------------------------------
# Row conversion helpers
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


def _experiment_from_row(row: ExperimentRow) -> Experiment:
    """Reconstruct an Experiment from a DB row."""
    return experiment_from_json(row.data)


# ---------------------------------------------------------------------------
# DB list helpers (domain-specific queries, not covered by base class)
# ---------------------------------------------------------------------------


async def _list_from_db(
    site_id: str | None = None,
    user_id: str | None = None,
) -> list[Experiment]:
    """List experiments from the database, optionally filtered by site and user."""
    stmt = select(ExperimentRow)
    if site_id:
        stmt = stmt.where(ExperimentRow.site_id == site_id)
    if user_id:
        stmt = stmt.where(ExperimentRow.user_id == user_id)
    stmt = stmt.order_by(ExperimentRow.created_at.desc())

    async with async_session_factory() as session:
        result = await session.execute(stmt)
        rows = result.scalars().all()
        return [_experiment_from_row(r) for r in rows]


async def _list_by_benchmark_from_db(benchmark_id: str) -> list[Experiment]:
    """List experiments from the database by benchmark_id."""
    stmt = select(ExperimentRow).where(ExperimentRow.benchmark_id == benchmark_id)
    async with async_session_factory() as session:
        result = await session.execute(stmt)
        rows = result.scalars().all()
        return [_experiment_from_row(r) for r in rows]


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


class ExperimentStore(WriteThruStore[Experiment]):
    """Experiment repository with in-memory cache and DB write-through.

    Inherits save/get/delete/aget/adelete from WriteThruStore.
    Adds domain-specific listing methods.
    """

    _model = ExperimentRow
    _to_row = staticmethod(_row_from_experiment)
    _from_row = staticmethod(_experiment_from_row)

    # -- Async listing (used by endpoint handlers) -------------------------

    async def alist_all(
        self, site_id: str | None = None, user_id: str | None = None
    ) -> list[Experiment]:
        """List experiments: merges DB rows with in-memory (fresher) state."""
        db_exps = await _list_from_db(site_id, user_id)
        merged: dict[str, Experiment] = {e.id: e for e in db_exps}
        # In-memory entries override DB (running experiments have fresher state)
        for eid, exp in self._cache.items():
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
        merged.update(
            {
                eid: exp
                for eid, exp in self._cache.items()
                if exp.benchmark_id == benchmark_id
            }
        )
        result = list(merged.values())
        result.sort(key=lambda e: (not e.is_primary_benchmark, e.created_at))
        return result


@cache
def get_experiment_store() -> ExperimentStore:
    """Get the global experiment store singleton."""
    return ExperimentStore()

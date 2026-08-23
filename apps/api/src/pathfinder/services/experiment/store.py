"""Experiment store that serves an in-memory cache and writes every mutation
through to the database."""

from datetime import UTC, datetime
from functools import cache

from assistant_core.platform.context import calling_application
from assistant_core.platform.db import async_session_factory
from sqlalchemy import select

from pathfinder.persistence.models import ExperimentRow
from pathfinder.platform.store import WriteThruStore
from pathfinder.services.experiment._deserialize import experiment_from_json
from pathfinder.services.experiment.types import (
    Experiment,
    experiment_to_json,
)


def _parse_created_at(iso_str: str) -> datetime:
    """Parse an ISO datetime string into a timezone-aware datetime."""
    if not iso_str:
        return datetime.now(UTC)
    dt = datetime.fromisoformat(iso_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _row_from_experiment(exp: Experiment) -> dict[str, object]:
    """Build the column values for an experiment row upsert."""
    return {
        "id": exp.id,
        "site_id": exp.config.site_id,
        "user_id": exp.user_id,
        "application_id": exp.application_id,
        "name": exp.config.name or "",
        "status": exp.status,
        "data": experiment_to_json(exp),
        "batch_id": exp.batch_id,
        "benchmark_id": exp.benchmark_id,
        "created_at": _parse_created_at(exp.created_at),
    }


def _experiment_from_row(row: ExperimentRow) -> Experiment:
    """Reconstruct an experiment from a database row.

    The column carries the application, not the serialized blob, so a row
    written before the column existed reads as the application it belongs to.
    """
    experiment = experiment_from_json(row.data)
    return experiment.model_copy(update={"application_id": row.application_id})


async def _list_from_db(
    site_id: str | None = None,
    user_id: str | None = None,
) -> list[Experiment]:
    """List experiments from the database with optional site and user
    filters."""
    stmt = select(ExperimentRow).where(
        ExperimentRow.application_id == calling_application(),
    )
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
    """List the experiments of one benchmark from the database."""
    stmt = select(ExperimentRow).where(
        ExperimentRow.benchmark_id == benchmark_id,
        ExperimentRow.application_id == calling_application(),
    )
    async with async_session_factory() as session:
        result = await session.execute(stmt)
        rows = result.scalars().all()
        return [_experiment_from_row(r) for r in rows]


class ExperimentStore(WriteThruStore[Experiment]):
    """Experiment repository with an in-memory cache and database
    write-through. Every read answers only for the calling application."""

    _model = ExperimentRow
    _to_row = staticmethod(_row_from_experiment)
    _from_row = staticmethod(_experiment_from_row)

    async def aget(self, entity_id: str) -> Experiment | None:
        exp = await super().aget(entity_id)
        if exp is None or exp.application_id != calling_application():
            return None
        return exp

    async def alist_all(
        self, site_id: str | None = None, user_id: str | None = None
    ) -> list[Experiment]:
        """List experiments from the database and the cache. A cached entry
        wins, because a running experiment holds the newer state."""
        db_exps = await _list_from_db(site_id, user_id)
        merged: dict[str, Experiment] = {e.id: e for e in db_exps}
        application_id = calling_application()
        for eid, exp in self._cache.items():
            if exp.application_id != application_id:
                continue
            if site_id and exp.config.site_id != site_id:
                continue
            if user_id and exp.user_id != user_id:
                continue
            merged[eid] = exp
        result = list(merged.values())
        result.sort(key=lambda e: e.created_at, reverse=True)
        return result

    async def alist_by_benchmark(self, benchmark_id: str) -> list[Experiment]:
        """List the experiments of one benchmark from the database and the
        cache."""
        db_exps = await _list_by_benchmark_from_db(benchmark_id)
        merged: dict[str, Experiment] = {e.id: e for e in db_exps}
        application_id = calling_application()
        merged.update(
            {
                eid: exp
                for eid, exp in self._cache.items()
                if exp.benchmark_id == benchmark_id
                and exp.application_id == application_id
            }
        )
        result = list(merged.values())
        result.sort(key=lambda e: (not e.is_primary_benchmark, e.created_at))
        return result


@cache
def get_experiment_store() -> ExperimentStore:
    """Return the process-wide experiment store."""
    return ExperimentStore()

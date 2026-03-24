"""Generic write-through store: in-memory cache + fire-and-forget DB persistence.

Provides the shared save/get/delete/aget/adelete logic so that concrete
stores only need to supply their ORM model class, row conversion functions,
and custom listing methods.

Subclasses define three class-level attributes:

* ``_model``    — SQLAlchemy ORM model class (e.g. ``ExperimentRow``)
* ``_to_row``   — callable mapping ``entity -> dict[str, object]`` for upsert
* ``_from_row`` — callable mapping ``row -> entity`` to reconstruct the domain object

The base class derives persist / load / delete from those, eliminating the
boilerplate that was previously duplicated across every concrete store.
"""

from collections.abc import Callable
from typing import Any, Protocol, cast

from sqlalchemy import delete as sa_delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from veupath_chatbot.persistence.session import async_session_factory
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.tasks import spawn

logger = get_logger(__name__)


class Identifiable(Protocol):
    """Any entity with a string ``id``."""

    @property
    def id(self) -> str: ...


class WriteThruStore[T: Identifiable]:
    """In-memory cache backed by fire-and-forget DB writes.

    Subclasses must set three class-level attributes:

    * ``_model``    — SQLAlchemy ORM model (must have an ``id`` column)
    * ``_to_row``   — ``(entity) -> dict`` of column values for upsert
    * ``_from_row`` — ``(row) -> T`` to reconstruct the entity from a DB row

    Every entity must satisfy the ``Identifiable`` protocol (have ``id: str``).
    """

    _model: Any = None  # SQLAlchemy ORM model class — set by subclass
    _to_row: Callable[[T], dict[str, object]] = cast(
        "Callable[[T], dict[str, object]]", cast("object", None)
    )
    _from_row: Callable[..., T] = cast("Callable[..., T]", cast("object", None))

    def __init__(self) -> None:
        self._cache: dict[str, T] = {}

    # -- DB helpers (derived from _model / _to_row / _from_row) ----------------

    async def _persist(self, entity: T) -> None:
        """Upsert an entity row into the database with retry on transient failures."""
        try:
            await self._persist_with_retry(entity)
        except Exception:
            logger.exception(
                "Failed to persist entity to DB",
                entity_type=self._model.__tablename__,
                entity_id=entity.id,
            )

    @retry(
        retry=retry_if_exception_type((OSError, ConnectionError, TimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.1, max=2),
        reraise=False,
    )
    async def _persist_with_retry(self, entity: T) -> None:
        vals = self._to_row(entity)
        stmt = (
            pg_insert(self._model)
            .values(**vals)
            .on_conflict_do_update(
                index_elements=[self._model.id],
                set_={k: v for k, v in vals.items() if k != "id"},
            )
        )
        async with async_session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    async def _load(self, entity_id: str) -> T | None:
        """Load a single entity from the database by primary key."""
        async with async_session_factory() as session:
            row = await session.get(self._model, entity_id)
            if row is None:
                return None
            return self._from_row(row)

    async def _delete_from_db(self, entity_id: str) -> None:
        """Delete an entity row from the database with retry on transient failures."""
        try:
            await self._delete_from_db_with_retry(entity_id)
        except Exception:
            logger.exception(
                "Failed to delete entity from DB",
                entity_type=self._model.__tablename__,
                entity_id=entity_id,
            )

    @retry(
        retry=retry_if_exception_type((OSError, ConnectionError, TimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.1, max=2),
        reraise=False,
    )
    async def _delete_from_db_with_retry(self, entity_id: str) -> None:
        stmt = sa_delete(self._model).where(self._model.id == entity_id)
        async with async_session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    # -- Sync interface ---------------------------------------------------

    def save(self, entity: T) -> None:
        self._cache[entity.id] = entity
        spawn(self._persist(entity), name=f"persist-{entity.id}")

    def get(self, entity_id: str) -> T | None:
        return self._cache.get(entity_id)

    def delete(self, entity_id: str) -> bool:
        removed = self._cache.pop(entity_id, None) is not None
        if removed:
            spawn(self._delete_from_db(entity_id), name=f"delete-{entity_id}")
        return removed

    # -- Async interface --------------------------------------------------

    async def aget(self, entity_id: str) -> T | None:
        entity = self._cache.get(entity_id)
        if entity is not None:
            return entity
        entity = await self._load(entity_id)
        if entity is not None:
            self._cache[entity_id] = entity
        return entity

    async def adelete(self, entity_id: str) -> bool:
        removed = entity_id in self._cache
        self._cache.pop(entity_id, None)
        await self._delete_from_db(entity_id)
        return removed

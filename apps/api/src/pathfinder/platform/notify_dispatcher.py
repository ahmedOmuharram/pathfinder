"""Process-wide multiplexing LISTEN dispatcher.

A single psycopg connection holds ``LISTEN`` on every channel any
subscriber cares about, and routes incoming ``NOTIFY`` messages to
per-subscriber asyncio queues. Subscribers (e.g. the task-events SSE
endpoint) register interest in a set of channel names, receive
``(channel, payload)`` tuples, and unregister on disconnect.

The alternative — one psycopg connection per SSE client — exhausts
Postgres' ``max_connections`` budget under load: at 200 concurrent
researchers watching tasks, that's 200 backends just for LISTEN.

Usage:
    dispatcher = NotifyDispatcher(database_url=...)
    await dispatcher.start()
    try:
        async with dispatcher.subscribe({"task_progress:abc",
                                         "chat_events:abc"}) as queue:
            channel, payload = await queue.get()
            ...
    finally:
        await dispatcher.close()

Opened once per process in the FastAPI ``lifespan`` context; the
worker does not need it.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

import psycopg
import psycopg.sql

from pathfinder.ai.chat.checkpointer import to_psycopg_url
from pathfinder.platform.logging import get_logger

logger = get_logger(__name__)


@dataclass
class _ChannelRegistry:
    """Ref-counted set of LISTENed channels.

    When the ref count for a channel drops to zero we UNLISTEN so the
    connection isn't pinned holding subscriptions that nothing is reading.
    """

    counts: dict[str, int] = field(default_factory=dict)

    def acquire(self, channels: frozenset[str]) -> list[str]:
        """Return channels whose ref count just went 0 → 1 (need LISTEN)."""
        newly_subscribed: list[str] = []
        for channel in channels:
            current = self.counts.get(channel, 0)
            if current == 0:
                newly_subscribed.append(channel)
            self.counts[channel] = current + 1
        return newly_subscribed

    def release(self, channels: frozenset[str]) -> list[str]:
        """Return channels whose ref count just went 1 → 0 (need UNLISTEN)."""
        freed: list[str] = []
        for channel in channels:
            current = self.counts.get(channel, 0)
            if current <= 1:
                freed.append(channel)
                self.counts.pop(channel, None)
            else:
                self.counts[channel] = current - 1
        return freed


@dataclass(eq=False)
class _Subscription:
    """One per ``subscribe()`` call.

    ``eq=False`` so instances hash by identity (default ``object.__hash__``).
    Without it, the dataclass-generated ``__eq__`` kills ``__hash__``, and
    we'd need a frozen type — but ``Queue`` isn't hashable anyway.
    """
    channels: frozenset[str]
    queue: asyncio.Queue[tuple[str, str]]


class NotifyDispatcher:
    """Singleton pg_notify multiplexer for the FastAPI process.

    Uses ONE psycopg connection for both the ``notifies()`` reader and
    LISTEN/UNLISTEN management. PostgreSQL binds LISTEN subscriptions to
    the session (connection), so LISTEN/UNLISTEN MUST run on the same
    connection the reader polls — a second "control" connection wouldn't
    see any NOTIFYs from LISTENs registered on it.

    Serialization works because ``notifies(timeout=<short>)`` yields the
    connection between polls, letting LISTEN/UNLISTEN cursors through.
    One connection instead of one-per-SSE-client is the whole point of
    this class; the budget is ``O(1)`` per process, not ``O(subscribers)``.
    """

    _QUEUE_MAXSIZE: int = 256
    _NOTIFIES_TIMEOUT_SECONDS: float = 0.5
    _RECONNECT_BACKOFF_SECONDS: tuple[float, ...] = (1.0, 2.0, 4.0, 8.0, 16.0)

    def __init__(self, *, database_url: str) -> None:
        self._database_url = database_url
        self._conn: psycopg.AsyncConnection[psycopg.rows.TupleRow] | None = None
        self._registry = _ChannelRegistry()
        self._subscriptions: set[_Subscription] = set()
        self._lock = asyncio.Lock()
        self._reader_task: asyncio.Task[None] | None = None
        self._closed = False

    async def start(self) -> None:
        """Open the connection + launch the NOTIFY reader.

        Idempotent — safe to call once per process in ``lifespan``.
        """
        if self._conn is not None:
            return
        conn_str = to_psycopg_url(self._database_url)
        self._conn = await psycopg.AsyncConnection.connect(
            conn_str, autocommit=True,
        )
        self._reader_task = asyncio.create_task(
            self._read_notifies(), name="notify-dispatcher",
        )
        logger.info("notify dispatcher started")

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        reader = self._reader_task
        conn = self._conn
        self._reader_task = None
        self._conn = None
        if reader is not None:
            reader.cancel()
            try:
                await reader
            except asyncio.CancelledError:
                logger.debug("notify reader cancelled on shutdown")
            except psycopg.OperationalError as exc:
                logger.info("notify reader closed during shutdown: %s", exc)
        if conn is not None:
            await conn.close()
        logger.info("notify dispatcher closed")

    @asynccontextmanager
    async def subscribe(
        self, channels: frozenset[str],
    ) -> AsyncIterator[asyncio.Queue[tuple[str, str]]]:
        """Yield a queue that receives ``(channel, payload)`` tuples.

        LISTEN is executed on the READER connection (that's where the
        subscription actually registers), via a small coordination step:
        the reader's ``notifies()`` loop has a timeout so it periodically
        releases the connection, letting LISTEN/UNLISTEN commands through.

        Queue is bounded — if the subscriber falls behind, new notifies
        are dropped and a warning is logged. SSE endpoints must drain
        promptly.
        """
        if self._conn is None:
            msg = "NotifyDispatcher.start() must be called first"
            raise RuntimeError(msg)
        queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue(
            maxsize=self._QUEUE_MAXSIZE,
        )
        subscription = _Subscription(channels=channels, queue=queue)
        async with self._lock:
            newly_subscribed = self._registry.acquire(channels)
            self._subscriptions.add(subscription)
            for channel in newly_subscribed:
                await self._execute_listen(channel)
        try:
            yield queue
        finally:
            async with self._lock:
                self._subscriptions.discard(subscription)
                freed = self._registry.release(channels)
                for channel in freed:
                    await self._execute_unlisten(channel)

    async def _execute_listen(self, channel: str) -> None:
        # LISTEN must share the session with ``notifies()``, so it runs
        # on the single pooled connection. The reader's polling timeout
        # (0.5s) serialized with these commands means LISTEN blocks for
        # at most that long before getting through.
        conn = self._require_conn()
        async with conn.cursor() as cur:
            await cur.execute(
                psycopg.sql.SQL("LISTEN {}").format(
                    psycopg.sql.Identifier(channel),
                ),
            )

    async def _execute_unlisten(self, channel: str) -> None:
        conn = self._require_conn()
        try:
            async with conn.cursor() as cur:
                await cur.execute(
                    psycopg.sql.SQL("UNLISTEN {}").format(
                        psycopg.sql.Identifier(channel),
                    ),
                )
        except (psycopg.Error, asyncio.CancelledError):
            # Dispatcher is closing — nothing else to do.
            pass

    def _require_conn(
        self,
    ) -> psycopg.AsyncConnection[psycopg.rows.TupleRow]:
        if self._conn is None:
            msg = "NotifyDispatcher connection is not open"
            raise RuntimeError(msg)
        return self._conn

    async def _read_notifies(self) -> None:
        """Drain NOTIFYs and reconnect on connection loss.

        Postgres restarts, network blips, and PgBouncer cycles drop the
        underlying connection. Without recovery, every SSE subscriber
        goes silent until the API is restarted. On ``OperationalError``
        we reopen the connection with exponential backoff and re-issue
        every currently-LISTENed channel so subscribers keep receiving
        notifies once the database is back.
        """
        while not self._closed:
            try:
                conn = self._require_conn()
                while not self._closed:
                    async for notify in conn.notifies(
                        timeout=self._NOTIFIES_TIMEOUT_SECONDS,
                    ):
                        self._fanout(notify.channel, notify.payload)
                    await asyncio.sleep(0)
            except asyncio.CancelledError:
                raise
            except psycopg.OperationalError:
                if self._closed:
                    return
                logger.exception("notify dispatcher connection dropped")
                reconnected = await self._reconnect_with_backoff()
                if not reconnected:
                    logger.warning("notify dispatcher reconnect abandoned")
                    return

    async def _reconnect_with_backoff(self) -> bool:
        """Reopen the connection + re-issue every LISTENed channel.

        Returns ``True`` when reconnection succeeded, ``False`` if the
        dispatcher was closed mid-backoff or all retries were exhausted.
        """
        conn_str = to_psycopg_url(self._database_url)
        for delay in self._RECONNECT_BACKOFF_SECONDS:
            if self._closed:
                return False
            try:
                await self._close_conn_if_open()
                self._conn = await psycopg.AsyncConnection.connect(
                    conn_str, autocommit=True,
                )
                async with self._lock:
                    for channel in self._registry.counts:
                        await self._execute_listen(channel)
            except psycopg.OperationalError:
                logger.warning(
                    "notify dispatcher reconnect failed; backing off %ss", delay,
                )
                await asyncio.sleep(delay)
            else:
                logger.info("notify dispatcher reconnected")
                return True
        return False

    async def _close_conn_if_open(self) -> None:
        conn = self._conn
        self._conn = None
        if conn is None:
            return
        # Connection is already broken in the reconnect path; best-effort
        # close — ignore psycopg errors so reconnect can proceed.
        with contextlib.suppress(psycopg.Error):
            await conn.close()

    def _fanout(self, channel: str, payload: str) -> None:
        # Deliver to every subscription that registered this channel.
        # Copy to tolerate concurrent subscribe/unsubscribe without holding
        # the lock across queue puts.
        snapshot = list(self._subscriptions)
        for subscription in snapshot:
            if channel not in subscription.channels:
                continue
            try:
                subscription.queue.put_nowait((channel, payload))
            except asyncio.QueueFull:
                logger.warning(
                    "dropping NOTIFY — subscriber queue full",
                    channel=channel,
                )


@asynccontextmanager
async def lifespan_notify_dispatcher(
    database_url: str,
) -> AsyncIterator[NotifyDispatcher]:
    dispatcher = NotifyDispatcher(database_url=database_url)
    await dispatcher.start()
    try:
        yield dispatcher
    finally:
        await dispatcher.close()

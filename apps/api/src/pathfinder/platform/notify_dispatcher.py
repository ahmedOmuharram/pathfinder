"""Process-wide multiplexing LISTEN dispatcher.

A single psycopg connection holds ``LISTEN`` on every channel any
subscriber cares about, and routes incoming ``NOTIFY`` messages to
per-subscriber asyncio queues. Subscribers (e.g. the task-events SSE
endpoint) register interest in a set of channel names, receive
``(channel, payload)`` tuples, and unregister on disconnect.

**Design — actor pattern.** Only the reader coroutine ever touches the
underlying connection. :meth:`subscribe` and unsubscribe paths only
mutate an in-memory registry and signal the reader with an
``asyncio.Event``. The reader owns the connection lifecycle end-to-end:

- opens on startup (with ``tenacity``-backed exponential retry)
- reconnects on ``psycopg.OperationalError`` (same retry policy)
- re-syncs LISTEN/UNLISTEN against the registry every wake-up

Subscribers can never observe a torn connection state, and there is no
lock contention between application code and reconnect logic because
application code never holds the connection.

The alternative — one psycopg connection per SSE client — exhausts
Postgres' ``max_connections`` budget under load: at 200 concurrent
researchers watching tasks, that's 200 backends just for LISTEN.

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
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from pathfinder.ai.chat.checkpointer import to_psycopg_url
from pathfinder.platform.logging import get_logger

logger = get_logger(__name__)


@dataclass
class _ChannelRegistry:
    """Ref-counted set of channels subscribers care about.

    The reader diffs this against its own ``_listened_channels`` to
    decide which LISTEN / UNLISTEN commands to issue. Nothing in this
    class talks to the database.
    """

    counts: dict[str, int] = field(default_factory=dict)

    def acquire(self, channels: frozenset[str]) -> None:
        for channel in channels:
            self.counts[channel] = self.counts.get(channel, 0) + 1

    def release(self, channels: frozenset[str]) -> None:
        for channel in channels:
            current = self.counts.get(channel, 0)
            if current <= 1:
                self.counts.pop(channel, None)
            else:
                self.counts[channel] = current - 1

    def desired_channels(self) -> set[str]:
        return set(self.counts.keys())


@dataclass(eq=False)
class _Subscription:
    """One per ``subscribe()`` call. Hashes by identity."""

    channels: frozenset[str]
    queue: asyncio.Queue[tuple[str, str]]


class NotifyDispatcher:
    """Singleton pg_notify multiplexer for the FastAPI process."""

    _QUEUE_MAXSIZE: int = 256
    _NOTIFIES_TIMEOUT_SECONDS: float = 0.2
    _CONNECT_MAX_ATTEMPTS: int = 6
    _CONNECT_WAIT_MIN_SECONDS: float = 1.0
    _CONNECT_WAIT_MAX_SECONDS: float = 16.0
    _SUBSCRIBE_SYNC_TIMEOUT_SECONDS: float = 5.0

    def __init__(self, *, database_url: str) -> None:
        self._database_url = database_url
        self._conn: psycopg.AsyncConnection[psycopg.rows.TupleRow] | None = None
        self._listened_channels: set[str] = set()
        self._registry = _ChannelRegistry()
        self._subscriptions: set[_Subscription] = set()
        self._intent_changed = asyncio.Event()
        self._pending_syncs: list[asyncio.Event] = []
        self._reader_task: asyncio.Task[None] | None = None
        self._closed = False

    async def start(self) -> None:
        """Launch the reader coroutine.

        The reader opens the connection itself (with retry); ``start``
        does not block on connection establishment. Idempotent — safe to
        call once per process in ``lifespan``.
        """
        if self._reader_task is not None:
            return
        self._reader_task = asyncio.create_task(
            self._reader_loop(), name="notify-dispatcher",
        )
        logger.info("notify dispatcher started")

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._intent_changed.set()  # wake reader so it sees ``_closed``
        reader = self._reader_task
        self._reader_task = None
        if reader is not None:
            reader.cancel()
            try:
                await reader
            except asyncio.CancelledError:
                logger.debug("notify reader cancelled on shutdown")
            except psycopg.OperationalError as exc:
                logger.info("notify reader closed during shutdown: %s", exc)
        await self._close_conn()
        logger.info("notify dispatcher closed")

    @asynccontextmanager
    async def subscribe(
        self, channels: frozenset[str],
    ) -> AsyncIterator[asyncio.Queue[tuple[str, str]]]:
        """Register interest in ``channels`` and yield a queue.

        Never touches the database. Updates the in-memory registry,
        signals the reader, and waits (up to
        :attr:`_SUBSCRIBE_SYNC_TIMEOUT_SECONDS`) for confirmation that
        LISTEN has been issued on the active connection before yielding
        — so callers can rely on NOTIFYs fired after ``subscribe``
        returns actually reaching the queue, even under reconnect.

        If the reader can't connect within the timeout, ``subscribe``
        still yields — the channel stays registered and delivery
        resumes once reconnect succeeds. Callers must replay durable
        state from the DB before trusting this stream for authoritative
        history (see ``/tasks/{id}/events`` :func:`_replay`).

        Queue is bounded (:attr:`_QUEUE_MAXSIZE`) — if the subscriber
        falls behind, new notifies are dropped and a warning is logged.
        """
        if self._reader_task is None:
            msg = "NotifyDispatcher.start() must be called first"
            raise RuntimeError(msg)
        queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue(
            maxsize=self._QUEUE_MAXSIZE,
        )
        subscription = _Subscription(channels=channels, queue=queue)
        sync_confirmed = asyncio.Event()
        self._registry.acquire(channels)
        self._subscriptions.add(subscription)
        self._pending_syncs.append(sync_confirmed)
        self._intent_changed.set()
        try:
            try:
                await asyncio.wait_for(
                    sync_confirmed.wait(),
                    timeout=self._SUBSCRIBE_SYNC_TIMEOUT_SECONDS,
                )
            except TimeoutError:
                logger.warning(
                    "subscribe timed out waiting for reader sync — "
                    "channels still registered",
                    channels=sorted(channels),
                )
            yield queue
        finally:
            self._subscriptions.discard(subscription)
            self._registry.release(channels)
            self._intent_changed.set()

    async def _reader_loop(self) -> None:
        """Own the connection lifecycle end-to-end.

        On every iteration:
        1. Ensure a healthy connection (reconnect with tenacity on failure).
        2. Sync LISTEN / UNLISTEN against the registry.
        3. Poll :meth:`notifies` with a short timeout.
        4. Fan out notifications; loop.

        On ``OperationalError`` the connection is discarded and step 1
        re-establishes it on the next iteration. ``_intent_changed``
        wakes the loop after subscribe/unsubscribe so step 2 re-syncs
        promptly.
        """
        while not self._closed:
            try:
                if self._conn is None:
                    await self._connect_with_retry()
                await self._sync_subscriptions()
                await self._drain_notifies_once()
            except asyncio.CancelledError:
                raise
            except psycopg.OperationalError:
                if self._closed:
                    return
                logger.warning(
                    "notify dispatcher connection lost; will reconnect",
                )
                await self._close_conn()
            except RuntimeError:
                # ``_connect_with_retry`` raises ``RuntimeError`` when
                # all tenacity attempts are exhausted. Stop the loop —
                # the lifespan owner will restart the process.
                logger.exception(
                    "notify dispatcher gave up — reconnect exhausted",
                )
                return

    async def _connect_with_retry(self) -> None:
        """Reopen the connection with exponential backoff via tenacity.

        Exhausted retries raise ``RuntimeError`` from the ``AsyncRetrying``
        context manager so the outer loop can terminate cleanly.
        """
        if self._closed:
            return
        conn_str = to_psycopg_url(self._database_url)
        retrying = AsyncRetrying(
            stop=stop_after_attempt(self._CONNECT_MAX_ATTEMPTS),
            wait=wait_exponential(
                multiplier=self._CONNECT_WAIT_MIN_SECONDS,
                max=self._CONNECT_WAIT_MAX_SECONDS,
            ),
            retry=retry_if_exception_type(psycopg.OperationalError),
            reraise=True,
        )
        async for attempt in retrying:
            with attempt:
                self._conn = await psycopg.AsyncConnection.connect(
                    conn_str, autocommit=True,
                )
                self._listened_channels.clear()  # new session
                logger.info("notify dispatcher connected")

    async def _sync_subscriptions(self) -> None:
        """Diff the registry against actual LISTENs; send the delta.

        After the delta is applied, any subscribers that were waiting
        on a sync confirmation are released (their
        ``sync_confirmed`` events are set). If the connection is
        missing we skip the DB work but still release waiters — the
        reconnect path calls us again after ``_connect_with_retry``
        succeeds, so waiters eventually see LISTEN.
        """
        self._intent_changed.clear()
        conn = self._conn
        if conn is not None:
            desired = self._registry.desired_channels()
            to_listen = desired - self._listened_channels
            to_unlisten = self._listened_channels - desired
            for channel in to_listen:
                async with conn.cursor() as cur:
                    await cur.execute(
                        psycopg.sql.SQL("LISTEN {}").format(
                            psycopg.sql.Identifier(channel),
                        ),
                    )
                self._listened_channels.add(channel)
            for channel in to_unlisten:
                async with conn.cursor() as cur:
                    await cur.execute(
                        psycopg.sql.SQL("UNLISTEN {}").format(
                            psycopg.sql.Identifier(channel),
                        ),
                    )
                self._listened_channels.discard(channel)
        # Release any subscribers waiting on this sync. Do this ONLY
        # when the connection is healthy so they know LISTEN is active.
        if conn is not None:
            pending = self._pending_syncs
            self._pending_syncs = []
            for event in pending:
                event.set()

    async def _drain_notifies_once(self) -> None:
        """One pass through the notifies iterator with a short timeout.

        The timeout yields the connection between iterations so the next
        ``_sync_subscriptions`` can run if the registry changed.
        """
        conn = self._conn
        if conn is None:
            return
        async for notify in conn.notifies(
            timeout=self._NOTIFIES_TIMEOUT_SECONDS,
        ):
            self._fanout(notify.channel, notify.payload)
        # Yield so intent-changed signal can propagate.
        await asyncio.sleep(0)

    async def _close_conn(self) -> None:
        conn = self._conn
        self._conn = None
        self._listened_channels.clear()
        if conn is None:
            return
        with contextlib.suppress(psycopg.Error):
            await conn.close()

    def _fanout(self, channel: str, payload: str) -> None:
        # Snapshot to tolerate concurrent subscribe/unsubscribe without
        # holding any lock during queue puts.
        for subscription in list(self._subscriptions):
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

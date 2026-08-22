"""Process-wide LISTEN dispatcher that multiplexes one connection over many subscribers.

Only the reader coroutine touches the connection. Subscribe and unsubscribe mutate an
in-memory registry and signal the reader, which owns the connection lifecycle.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

import psycopg
import psycopg.rows
import psycopg.sql
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from pathfinder.assistant_core.conversation.checkpointer import to_psycopg_url
from pathfinder.platform.logging import get_logger

logger = get_logger(__name__)


@dataclass
class _ChannelRegistry:
    """Reference-counted set of the channels subscribers want. This class does no
    database work; the reader diffs it against the active LISTENs."""

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
    """One record per subscribe call. It hashes by identity."""

    channels: frozenset[str]
    queue: asyncio.Queue[tuple[str, str]]


class NotifyDispatcher:
    """Multiplexes pg_notify channels for one process."""

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
        """Starts the reader coroutine. The reader opens the connection itself, so
        this call does not block. A second call has no effect."""
        if self._reader_task is not None:
            return
        self._reader_task = asyncio.create_task(
            self._reader_loop(),
            name="notify-dispatcher",
        )
        logger.info("notify dispatcher started")

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._intent_changed.set()  # Wake the reader so it sees the closed flag.
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
        self,
        channels: frozenset[str],
    ) -> AsyncIterator[asyncio.Queue[tuple[str, str]]]:
        """Registers interest in the channels and yields a bounded queue.

        The call waits for the reader to confirm LISTEN, then yields even if the
        timeout expires. The stream is not authoritative history, so a caller that
        needs history replays durable state from the database first.
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
        """Owns the connection lifecycle.

        Each pass makes sure a connection exists, syncs LISTEN and UNLISTEN against
        the registry, polls for notifications, and fans them out.
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
                # Reconnect raises RuntimeError when all attempts fail. The loop stops
                # and the lifespan owner restarts the process.
                logger.exception(
                    "notify dispatcher gave up — reconnect exhausted",
                )
                return

    async def _connect_with_retry(self) -> None:
        """Reopens the connection with exponential backoff. Exhausted retries raise
        RuntimeError so the outer loop stops."""
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
                    conn_str,
                    autocommit=True,
                )
                self._listened_channels.clear()  # A new session holds no LISTEN.
                logger.info("notify dispatcher connected")

    async def _sync_subscriptions(self) -> None:
        """Diffs the registry against the active LISTENs and sends the delta.

        Waiting subscribers are released only when the connection is healthy, so a
        released waiter knows LISTEN is active.
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
        if conn is not None:
            pending = self._pending_syncs
            self._pending_syncs = []
            for event in pending:
                event.set()

    async def _drain_notifies_once(self) -> None:
        """Makes one pass through the notifies iterator with a short timeout, so the
        next sync can run when the registry changes."""
        conn = self._conn
        if conn is None:
            return
        async for notify in conn.notifies(
            timeout=self._NOTIFIES_TIMEOUT_SECONDS,
        ):
            self._fanout(notify.channel, notify.payload)
        # Yield so the intent-changed signal propagates.
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
        # Snapshot the set so concurrent subscribe and unsubscribe need no lock.
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

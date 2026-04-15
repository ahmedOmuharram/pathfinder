"""Direct tests for :class:`NotifyDispatcher`.

Exercises subscribe/unsubscribe ref counting, fanout across multiple
subscribers, queue-full drop behavior, and reconnect on connection loss.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable

import psycopg
import psycopg.sql
import pytest

from pathfinder.ai.chat.checkpointer import to_psycopg_url
from pathfinder.platform.notify_dispatcher import (
    NotifyDispatcher,
    lifespan_notify_dispatcher,
)


async def _notify(database_url: str, channel: str, payload: str) -> None:
    """Fire pg_notify from a separate connection (not the dispatcher's)."""
    conn_str = to_psycopg_url(database_url)
    async with await psycopg.AsyncConnection.connect(
        conn_str, autocommit=True,
    ) as aconn, aconn.cursor() as cur:
        await cur.execute(
            psycopg.sql.SQL("SELECT pg_notify({}, {})").format(
                psycopg.sql.Literal(channel),
                psycopg.sql.Literal(payload),
            ),
        )


async def _drain_until(
    queue: asyncio.Queue[tuple[str, str]],
    predicate: "Callable[[tuple[str, str]], bool]",
    *,
    deadline_seconds: float = 3.0,
) -> list[tuple[str, str]]:
    received: list[tuple[str, str]] = []
    loop = asyncio.get_running_loop()
    end_at = loop.time() + deadline_seconds
    while loop.time() < end_at:
        remaining = end_at - loop.time()
        try:
            async with asyncio.timeout(remaining):
                item = await queue.get()
        except TimeoutError:
            break
        received.append(item)
        if predicate(item):
            return received
    return received


@pytest.mark.asyncio
async def test_subscribe_receives_notify(
    patch_app_db_engine: None,
) -> None:
    del patch_app_db_engine
    database_url = os.environ["DATABASE_URL"]
    async with (
        lifespan_notify_dispatcher(database_url) as dispatcher,
        dispatcher.subscribe(frozenset({"pf_test_ch_1"})) as queue,
    ):
        await asyncio.sleep(0.1)  # let LISTEN register
        await _notify(database_url, "pf_test_ch_1", "hello")
        received = await _drain_until(
            queue, lambda item: item == ("pf_test_ch_1", "hello"),
        )
        assert ("pf_test_ch_1", "hello") in received


@pytest.mark.asyncio
async def test_two_subscribers_share_one_listen(
    patch_app_db_engine: None,
) -> None:
    """Registry ref-counts channels so each channel is LISTENed once."""
    del patch_app_db_engine
    database_url = os.environ["DATABASE_URL"]
    async with (
        lifespan_notify_dispatcher(database_url) as dispatcher,
        dispatcher.subscribe(frozenset({"pf_test_ch_2"})) as q1,
        dispatcher.subscribe(frozenset({"pf_test_ch_2"})) as q2,
    ):
        await asyncio.sleep(0.1)
        await _notify(database_url, "pf_test_ch_2", "msg")
        got_q1 = await _drain_until(
            q1, lambda item: item == ("pf_test_ch_2", "msg"),
        )
        got_q2 = await _drain_until(
            q2, lambda item: item == ("pf_test_ch_2", "msg"),
        )
        assert ("pf_test_ch_2", "msg") in got_q1
        assert ("pf_test_ch_2", "msg") in got_q2


@pytest.mark.asyncio
async def test_unsubscribe_stops_delivery(
    patch_app_db_engine: None,
) -> None:
    """Leaving the subscribe context unregisters the channel."""
    del patch_app_db_engine
    database_url = os.environ["DATABASE_URL"]
    async with lifespan_notify_dispatcher(database_url) as dispatcher:
        async with dispatcher.subscribe(frozenset({"pf_test_ch_3"})):
            pass  # immediately exits — unsubscribe fires
        await _notify(database_url, "pf_test_ch_3", "ignored")
        await asyncio.sleep(0.3)  # settle
        # No assertion on delivery — the point is nothing crashes after
        # unsubscribe. Re-subscribing to the same channel must still work.
        async with dispatcher.subscribe(frozenset({"pf_test_ch_3"})) as q2:
            await asyncio.sleep(0.1)
            await _notify(database_url, "pf_test_ch_3", "delivered")
            received = await _drain_until(
                q2, lambda item: item == ("pf_test_ch_3", "delivered"),
            )
            assert ("pf_test_ch_3", "delivered") in received


@pytest.mark.asyncio
async def test_fanout_respects_channel_filter(
    patch_app_db_engine: None,
) -> None:
    """Subscribers only get notifies for the channels they actually asked for."""
    del patch_app_db_engine
    database_url = os.environ["DATABASE_URL"]
    async with (
        lifespan_notify_dispatcher(database_url) as dispatcher,
        dispatcher.subscribe(frozenset({"pf_test_ch_a"})) as qa,
        dispatcher.subscribe(frozenset({"pf_test_ch_b"})) as qb,
    ):
        await asyncio.sleep(0.1)
        await _notify(database_url, "pf_test_ch_a", "for_a")
        await _notify(database_url, "pf_test_ch_b", "for_b")
        got_a = await _drain_until(
            qa, lambda item: item[0] == "pf_test_ch_a",
            deadline_seconds=2.0,
        )
        got_b = await _drain_until(
            qb, lambda item: item[0] == "pf_test_ch_b",
            deadline_seconds=2.0,
        )
        assert all(ch == "pf_test_ch_a" for ch, _ in got_a)
        assert all(ch == "pf_test_ch_b" for ch, _ in got_b)


@pytest.mark.asyncio
async def test_close_is_idempotent(patch_app_db_engine: None) -> None:
    del patch_app_db_engine
    database_url = os.environ["DATABASE_URL"]
    dispatcher = NotifyDispatcher(database_url=database_url)
    await dispatcher.start()
    await dispatcher.close()
    # Second close must not raise.
    await dispatcher.close()


@pytest.mark.asyncio
async def test_start_is_idempotent(patch_app_db_engine: None) -> None:
    del patch_app_db_engine
    database_url = os.environ["DATABASE_URL"]
    dispatcher = NotifyDispatcher(database_url=database_url)
    try:
        await dispatcher.start()
        # Second start must not raise or clobber state.
        await dispatcher.start()
    finally:
        await dispatcher.close()


@pytest.mark.asyncio
async def test_reconnect_restores_delivery_after_connection_loss(
    patch_app_db_engine: None,
) -> None:
    """Simulate a dropped connection and verify the reconnect path works.

    Production-critical: Postgres restarts, network blips, PgBouncer cycles
    all drop the dispatcher's pooled connection. Without recovery, every
    SSE subscriber goes silent. This test force-closes ``_conn`` to trigger
    ``OperationalError`` in ``notifies()``, then asserts the same subscriber
    receives a NOTIFY fired AFTER reconnect — no resubscribe required.
    """
    del patch_app_db_engine
    database_url = os.environ["DATABASE_URL"]
    dispatcher = NotifyDispatcher(database_url=database_url)
    dispatcher._RECONNECT_BACKOFF_SECONDS = (0.1, 0.1, 0.2)  # speed up test
    await dispatcher.start()
    try:
        async with dispatcher.subscribe(frozenset({"pf_test_reconn"})) as queue:
            await asyncio.sleep(0.1)  # let initial LISTEN register
            # Force-close the connection — simulates an OperationalError in
            # the reader loop's ``notifies()`` iteration.
            closing_conn = dispatcher._conn
            assert closing_conn is not None
            await closing_conn.close()
            # Wait for reconnect + re-LISTEN. Backoff is ~0.1s, plus LISTEN
            # re-issue; give it a generous window.
            await asyncio.sleep(1.0)
            # Confirm a fresh connection was established.
            assert dispatcher._conn is not None
            assert dispatcher._conn is not closing_conn
            # Fire a NOTIFY; the existing subscriber must receive it.
            await _notify(database_url, "pf_test_reconn", "after_reconnect")
            received = await _drain_until(
                queue,
                lambda item: item == ("pf_test_reconn", "after_reconnect"),
                deadline_seconds=3.0,
            )
            assert ("pf_test_reconn", "after_reconnect") in received
    finally:
        await dispatcher.close()

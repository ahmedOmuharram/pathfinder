"""Tests for the notify dispatcher: subscription, fanout and reconnect."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable

import psycopg
import psycopg.sql
import pytest

from pathfinder.assistant_core.conversation.checkpointer import to_psycopg_url
from pathfinder.platform.notify_dispatcher import (
    NotifyDispatcher,
    lifespan_notify_dispatcher,
)


async def _notify(database_url: str, channel: str, payload: str) -> None:
    """Fire a notify from a connection other than the dispatcher's."""
    conn_str = to_psycopg_url(database_url)
    async with (
        await psycopg.AsyncConnection.connect(
            conn_str,
            autocommit=True,
        ) as aconn,
        aconn.cursor() as cur,
    ):
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
        await asyncio.sleep(0.1)  # Let the listen register.
        await _notify(database_url, "pf_test_ch_1", "hello")
        received = await _drain_until(
            queue,
            lambda item: item == ("pf_test_ch_1", "hello"),
        )
        assert ("pf_test_ch_1", "hello") in received


@pytest.mark.asyncio
async def test_two_subscribers_share_one_listen(
    patch_app_db_engine: None,
) -> None:
    """The registry counts references, so each channel gets one listen."""
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
            q1,
            lambda item: item == ("pf_test_ch_2", "msg"),
        )
        got_q2 = await _drain_until(
            q2,
            lambda item: item == ("pf_test_ch_2", "msg"),
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
            pass  # The context exits at once, which unsubscribes.
        await _notify(database_url, "pf_test_ch_3", "ignored")
        await asyncio.sleep(0.3)
        # A second subscription to the same channel must still deliver.
        async with dispatcher.subscribe(frozenset({"pf_test_ch_3"})) as q2:
            await asyncio.sleep(0.1)
            await _notify(database_url, "pf_test_ch_3", "delivered")
            received = await _drain_until(
                q2,
                lambda item: item == ("pf_test_ch_3", "delivered"),
            )
            assert ("pf_test_ch_3", "delivered") in received


@pytest.mark.asyncio
async def test_fanout_respects_channel_filter(
    patch_app_db_engine: None,
) -> None:
    """A subscriber gets notifies for its own channels only."""
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
            qa,
            lambda item: item[0] == "pf_test_ch_a",
            deadline_seconds=2.0,
        )
        got_b = await _drain_until(
            qb,
            lambda item: item[0] == "pf_test_ch_b",
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
async def test_subscribe_on_dead_connection_does_not_raise(
    patch_app_db_engine: None,
) -> None:
    """Subscribe changes the in-memory registry only, so it raises no connection error.

    The next reconnect issues the listen for the recorded channel.
    """
    del patch_app_db_engine
    database_url = os.environ["DATABASE_URL"]
    dispatcher = NotifyDispatcher(database_url=database_url)
    await dispatcher.start()
    try:
        # Let the reader open the first connection.
        await asyncio.sleep(0.2)
        closing_conn = dispatcher._conn
        assert closing_conn is not None
        await closing_conn.close()
        # Subscribe while the connection is dead.
        async with dispatcher.subscribe(
            frozenset({"pf_subscribe_on_dead"}),
        ):
            assert "pf_subscribe_on_dead" in dispatcher._registry.counts
    finally:
        await dispatcher.close()


@pytest.mark.asyncio
async def test_reconnect_restores_delivery_after_connection_loss(
    patch_app_db_engine: None,
) -> None:
    """A subscriber keeps its delivery across a dropped connection.

    The reconnect needs no action from the subscriber.
    """
    del patch_app_db_engine
    database_url = os.environ["DATABASE_URL"]
    dispatcher = NotifyDispatcher(database_url=database_url)
    dispatcher._CONNECT_WAIT_MIN_SECONDS = 0.1  # Shorten the backoff.
    dispatcher._CONNECT_WAIT_MAX_SECONDS = 0.2
    await dispatcher.start()
    try:
        async with dispatcher.subscribe(frozenset({"pf_test_reconn"})) as queue:
            await asyncio.sleep(0.1)  # Let the first listen register.
            # Close the connection, which makes the reader loop fail.
            closing_conn = dispatcher._conn
            assert closing_conn is not None
            await closing_conn.close()
            # Wait for the reconnect and the new listen.
            await asyncio.sleep(1.0)
            assert dispatcher._conn is not None
            assert dispatcher._conn is not closing_conn
            await _notify(database_url, "pf_test_reconn", "after_reconnect")
            received = await _drain_until(
                queue,
                lambda item: item == ("pf_test_reconn", "after_reconnect"),
                deadline_seconds=3.0,
            )
            assert ("pf_test_reconn", "after_reconnect") in received
    finally:
        await dispatcher.close()

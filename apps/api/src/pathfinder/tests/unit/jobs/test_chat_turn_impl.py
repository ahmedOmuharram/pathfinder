"""Worker boundary: run_chat_turn sets the ctxvar from the payload."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

import pytest

from pathfinder.ai.conversation.request_body import ChatRequestBody
from pathfinder.jobs.impls import chat_turn_impl as chat_turn_impl_mod
from pathfinder.jobs.impls.chat_turn_impl import run_chat_turn
from pathfinder.jobs.payloads import ChatTurnPayload
from pathfinder.platform.context import veupathdb_auth_token_ctx


def _body() -> ChatRequestBody:
    return ChatRequestBody.model_validate(
        {
            "conversationId": str(uuid4()),
            "messages": [
                {
                    "id": str(uuid4()),
                    "role": "user",
                    "parts": [{"type": "text", "text": "hi"}],
                },
            ],
            "siteId": "plasmodb",
        },
    )


class _FakeGraph:
    async def ainvoke(self, *args: object, **kwargs: object) -> None:
        del args, kwargs


@asynccontextmanager
async def _fake_checkpointer_ctx(*args: object, **kwargs: object) -> AsyncIterator[None]:
    del args, kwargs
    yield None


@asynccontextmanager
async def _fake_memory_ctx(*args: object, **kwargs: object) -> AsyncIterator[None]:
    del args, kwargs
    yield None


def _fake_build_graph(*args: object, **kwargs: object) -> _FakeGraph:
    del args, kwargs
    return _FakeGraph()


class _ObservingRunTurn:
    """Records the ctxvar value at the moment run_turn is invoked."""

    def __init__(self) -> None:
        self.observed_token: str | None | object = _sentinel
        self.call_count = 0

    async def __call__(self, **kwargs: Any) -> None:
        del kwargs
        self.observed_token = veupathdb_auth_token_ctx.get()
        self.call_count += 1


_sentinel = object()


@pytest.mark.asyncio
async def test_run_chat_turn_sets_ctxvar_from_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observer = _ObservingRunTurn()
    monkeypatch.setattr(chat_turn_impl_mod, "run_turn", observer)
    monkeypatch.setattr(
        chat_turn_impl_mod, "lifespan_checkpointer", _fake_checkpointer_ctx,
    )
    monkeypatch.setattr(
        chat_turn_impl_mod, "lifespan_memory_store", _fake_memory_ctx,
    )
    monkeypatch.setattr(chat_turn_impl_mod, "build_graph", _fake_build_graph)

    payload = ChatTurnPayload(
        body=_body(),
        user_id=uuid4(),
        turn_id=uuid4(),
        veupathdb_auth_token="user-token-abc",
    )

    await run_chat_turn(payload.model_dump(mode="json", by_alias=True))

    assert observer.call_count == 1
    assert observer.observed_token == "user-token-abc"


@pytest.mark.asyncio
async def test_run_chat_turn_resets_ctxvar_after_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observer = _ObservingRunTurn()
    monkeypatch.setattr(chat_turn_impl_mod, "run_turn", observer)
    monkeypatch.setattr(
        chat_turn_impl_mod, "lifespan_checkpointer", _fake_checkpointer_ctx,
    )
    monkeypatch.setattr(
        chat_turn_impl_mod, "lifespan_memory_store", _fake_memory_ctx,
    )
    monkeypatch.setattr(chat_turn_impl_mod, "build_graph", _fake_build_graph)

    assert veupathdb_auth_token_ctx.get() is None
    payload = ChatTurnPayload(
        body=_body(),
        user_id=uuid4(),
        turn_id=uuid4(),
        veupathdb_auth_token="user-token-xyz",
    )
    await run_chat_turn(payload.model_dump(mode="json", by_alias=True))
    assert veupathdb_auth_token_ctx.get() is None


@pytest.mark.asyncio
async def test_run_chat_turn_tolerates_missing_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An anonymous caller (no cookie) dispatches with token=None. The
    worker still runs — WDK calls fall through to settings (service)."""
    observer = _ObservingRunTurn()
    monkeypatch.setattr(chat_turn_impl_mod, "run_turn", observer)
    monkeypatch.setattr(
        chat_turn_impl_mod, "lifespan_checkpointer", _fake_checkpointer_ctx,
    )
    monkeypatch.setattr(
        chat_turn_impl_mod, "lifespan_memory_store", _fake_memory_ctx,
    )
    monkeypatch.setattr(chat_turn_impl_mod, "build_graph", _fake_build_graph)

    payload = ChatTurnPayload(
        body=_body(),
        user_id=uuid4(),
        turn_id=uuid4(),
    )
    await run_chat_turn(payload.model_dump(mode="json", by_alias=True))

    assert observer.observed_token is None

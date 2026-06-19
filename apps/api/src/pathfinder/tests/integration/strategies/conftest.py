from __future__ import annotations

import contextlib
import os
from collections.abc import AsyncGenerator, Awaitable, Callable
from dataclasses import dataclass
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pathfinder.domain.parameters.values import (
    MultiPickValue,
    SinglePickValue,
    StringValue,
)
from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.domain.strategy.build_outcome import BuildOutcome
from pathfinder.domain.strategy.strategy_ast import PersistedStrategyGraph, StrategyAst
from pathfinder.integrations.veupathdb.factory import (
    get_results_api,
    get_strategy_api,
)
from pathfinder.persistence.models import Conversation, User
from pathfinder.platform.context import veupathdb_auth_token_ctx
from pathfinder.platform.db import async_session_factory
from pathfinder.services.strategies.context import StrategyMutationContext
from pathfinder.services.strategies.session_factory import build_strategy_session
from pathfinder.services.strategies.spec_build import build_strategy_from_spec
from pathfinder.services.strategies.wdk_conversion import (
    build_snapshot_from_wdk,
    canonicalize_synced_parameters,
)


@dataclass
class RoundTrip:
    outcome: BuildOutcome
    decoded: StrategyAst
    wdk_strategy_id: int


BuildAndRead = Callable[[StrategyStepNode], Awaitable[RoundTrip]]
BuildRaw = Callable[[StrategyStepNode], Awaitable[BuildOutcome]]

ORGANISM = "Plasmodium falciparum 3D7"


def text_leaf(expression: str) -> StrategyStepNode:
    return StrategyStepNode(
        id="leaf",
        search_name="GenesByText",
        parameters={
            "text_expression": StringValue(value=expression),
            "text_fields": MultiPickValue(values=["product"]),
            "document_type": StringValue(value="gene"),
            "text_search_organism": MultiPickValue(values=[ORGANISM]),
        },
    )


def go_term_leaf(go_id: str) -> StrategyStepNode:
    return StrategyStepNode(
        id="go",
        search_name="GenesByGoTerm",
        parameters={
            "organism": MultiPickValue(values=[ORGANISM]),
            "go_term_evidence": MultiPickValue(values=["Curated", "Computed"]),
            "go_term_slim": SinglePickValue(value="No"),
            "go_typeahead": MultiPickValue(values=[go_id]),
            "go_term": StringValue(value=go_id),
        },
    )


async def step_gene_ids(rt: RoundTrip) -> tuple[int, set[str]]:
    assert rt.decoded.wdk_step_ids
    step = next(iter(rt.decoded.wdk_step_ids.values()))
    answer = await get_results_api("plasmodb").get_step_preview(step, limit=50000)
    return step, {r.display_name for r in answer.records}


@pytest.fixture
def require_wdk_creds() -> None:
    if not (os.environ.get("WDK_TEST_EMAIL") and os.environ.get("WDK_TEST_PASSWORD")):
        pytest.skip("set WDK_TEST_EMAIL/WDK_TEST_PASSWORD to run live WDK tests")


@pytest.fixture
async def wdk_session(
    app: FastAPI,
    patch_app_db_engine: None,
    db_cleaner: None,
) -> AsyncGenerator[None]:
    """Authenticate the WDK client as the real account (no build machinery)."""
    del patch_app_db_engine, db_cleaner
    email = os.environ.get("WDK_TEST_EMAIL", "")
    password = os.environ.get("WDK_TEST_PASSWORD", "")
    if not email or not password:
        pytest.skip("set WDK_TEST_EMAIL/WDK_TEST_PASSWORD to run live WDK tests")
    token = await _real_account_token(app, email, password)
    reset = veupathdb_auth_token_ctx.set(token)
    try:
        yield
    finally:
        veupathdb_auth_token_ctx.reset(reset)


async def _real_account_token(app: FastAPI, email: str, password: str) -> str:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-Requested-With": "XMLHttpRequest"},
    ) as client:
        resp = await client.post(
            "/api/v1/veupathdb/auth/login",
            params={"siteId": "plasmodb"},
            json={"email": email, "password": password},
        )
        assert resp.status_code == 200, resp.text
        token = client.cookies.get("Authorization")
    assert token, "login did not set an Authorization cookie"
    return token


@pytest.fixture
async def wdk_builder(
    app: FastAPI,
    patch_app_db_engine: None,
    session_maker: async_sessionmaker[AsyncSession],
    db_cleaner: None,
) -> AsyncGenerator[BuildAndRead]:
    del patch_app_db_engine, db_cleaner
    email = os.environ.get("WDK_TEST_EMAIL", "")
    password = os.environ.get("WDK_TEST_PASSWORD", "")
    if not email or not password:
        pytest.skip("set WDK_TEST_EMAIL/WDK_TEST_PASSWORD to run live WDK tests")

    token = await _real_account_token(app, email, password)
    reset = veupathdb_auth_token_ctx.set(token)
    created: list[int] = []

    async def build_and_read(root: StrategyStepNode) -> RoundTrip:
        async with session_maker() as session:
            user_id, conv_id = uuid4(), uuid4()
            session.add(User(id=user_id))
            session.add(
                Conversation(id=conv_id, user_id=user_id, site_id="plasmodb", name="rt")
            )
            await session.commit()
        strategy_session = build_strategy_session(
            site_id="plasmodb",
            strategy_graph=PersistedStrategyGraph(
                id=str(conv_id), name="rt", strategy_ast=None, wdk_strategy_id=None
            ),
        )
        outcome = await build_strategy_from_spec(
            deps=StrategyMutationContext(
                site_id="plasmodb",
                strategy_session=strategy_session,
                conversation_id=conv_id,
                db_session_factory=async_session_factory,
            ),
            root=root,
            name="rt",
        )
        assert outcome.failed_steps == [], outcome.failed_steps
        assert outcome.wdk_strategy_id is not None
        created.append(outcome.wdk_strategy_id)
        api = get_strategy_api("plasmodb")
        saved = await api.get_strategy(outcome.wdk_strategy_id)
        ast, wire = build_snapshot_from_wdk(saved)
        await canonicalize_synced_parameters(ast, api, wire)
        return RoundTrip(
            outcome=outcome, decoded=ast, wdk_strategy_id=outcome.wdk_strategy_id
        )

    try:
        yield build_and_read
    finally:
        api = get_strategy_api("plasmodb")
        for sid in created:
            with contextlib.suppress(Exception):
                await api.delete_strategy(sid)
        veupathdb_auth_token_ctx.reset(reset)


@pytest.fixture
async def wdk_build_raw(
    app: FastAPI,
    patch_app_db_engine: None,
    session_maker: async_sessionmaker[AsyncSession],
    db_cleaner: None,
) -> AsyncGenerator[BuildRaw]:
    del patch_app_db_engine, db_cleaner
    email = os.environ.get("WDK_TEST_EMAIL", "")
    password = os.environ.get("WDK_TEST_PASSWORD", "")
    if not email or not password:
        pytest.skip("set WDK_TEST_EMAIL/WDK_TEST_PASSWORD to run live WDK tests")

    token = await _real_account_token(app, email, password)
    reset = veupathdb_auth_token_ctx.set(token)
    created: list[int] = []

    async def build_raw(root: StrategyStepNode) -> BuildOutcome:
        async with session_maker() as session:
            user_id, conv_id = uuid4(), uuid4()
            session.add(User(id=user_id))
            session.add(
                Conversation(
                    id=conv_id, user_id=user_id, site_id="plasmodb", name="rt-raw"
                )
            )
            await session.commit()
        strategy_session = build_strategy_session(
            site_id="plasmodb",
            strategy_graph=PersistedStrategyGraph(
                id=str(conv_id), name="rt-raw", strategy_ast=None, wdk_strategy_id=None
            ),
        )
        outcome = await build_strategy_from_spec(
            deps=StrategyMutationContext(
                site_id="plasmodb",
                strategy_session=strategy_session,
                conversation_id=conv_id,
                db_session_factory=async_session_factory,
            ),
            root=root,
            name="rt-raw",
        )
        if outcome.wdk_strategy_id is not None:
            created.append(outcome.wdk_strategy_id)
        return outcome

    try:
        yield build_raw
    finally:
        api = get_strategy_api("plasmodb")
        for sid in created:
            with contextlib.suppress(Exception):
                await api.delete_strategy(sid)
        veupathdb_auth_token_ctx.reset(reset)

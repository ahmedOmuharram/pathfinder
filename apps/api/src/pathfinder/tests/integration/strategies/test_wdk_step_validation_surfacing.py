from __future__ import annotations

import contextlib
import os
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from uuid import uuid4

import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pathfinder.domain.parameters.values import MultiPickValue, StringValue
from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.strategy_ast import PersistedStrategyGraph, StrategyAst
from pathfinder.domain.strategy.validation import StepValidation
from pathfinder.integrations.veupathdb.factory import get_strategy_api
from pathfinder.persistence.models import Conversation, User
from pathfinder.platform.context import veupathdb_auth_token_ctx
from pathfinder.platform.db import async_session_factory
from pathfinder.services.strategies.context import StrategyMutationContext
from pathfinder.services.strategies.session_factory import build_strategy_session
from pathfinder.services.strategies.spec_build import build_strategy_from_spec
from pathfinder.services.strategies.sync_state import ensure_sync_state
from pathfinder.tests.integration.strategies.conftest import _real_account_token

pytestmark = [pytest.mark.live_wdk, pytest.mark.asyncio]

_ORG = "Plasmodium falciparum 3D7"


def _text_leaf(step_id: str, expression: str) -> StrategyStepNode:
    return StrategyStepNode(
        id=step_id,
        search_name="GenesByText",
        parameters={
            "text_expression": StringValue(value=expression),
            "text_fields": MultiPickValue(values=["product"]),
            "document_type": StringValue(value="gene"),
            "text_search_organism": MultiPickValue(values=[_ORG]),
        },
    )


@dataclass
class _Built:
    deps: StrategyMutationContext
    conv_id: object
    session_maker: async_sessionmaker[AsyncSession]


@pytest.fixture
async def built_union(
    app: FastAPI,
    patch_app_db_engine: None,
    session_maker: async_sessionmaker[AsyncSession],
    db_cleaner: None,
) -> AsyncGenerator[_Built]:
    del patch_app_db_engine, db_cleaner
    email = os.environ.get("WDK_TEST_EMAIL", "")
    password = os.environ.get("WDK_TEST_PASSWORD", "")
    if not email or not password:
        pytest.skip("set WDK_TEST_EMAIL/WDK_TEST_PASSWORD to run live WDK tests")
    token = await _real_account_token(app, email, password)
    reset = veupathdb_auth_token_ctx.set(token)
    created: list[int] = []
    user_id, conv_id = uuid4(), uuid4()
    async with session_maker() as session:
        session.add(User(id=user_id))
        session.add(
            Conversation(id=conv_id, user_id=user_id, site_id="plasmodb", name="val")
        )
        await session.commit()
    deps = StrategyMutationContext(
        site_id="plasmodb",
        strategy_session=build_strategy_session(
            site_id="plasmodb",
            strategy_graph=PersistedStrategyGraph(
                id=str(conv_id), name="val", strategy_ast=None, wdk_strategy_id=None
            ),
        ),
        conversation_id=conv_id,
        db_session_factory=async_session_factory,
    )
    root = StrategyStepNode(
        id="combine",
        search_name="__combine__",
        operator=CombineOp.UNION,
        primary_input=_text_leaf("kinase", "kinase"),
        secondary_input=_text_leaf("phosphatase", "phosphatase"),
    )
    outcome = await build_strategy_from_spec(deps=deps, root=root, name="val")
    assert outcome.failed_steps == [], outcome.failed_steps
    assert outcome.wdk_strategy_id is not None
    created.append(outcome.wdk_strategy_id)
    try:
        yield _Built(deps=deps, conv_id=conv_id, session_maker=session_maker)
    finally:
        api = get_strategy_api("plasmodb")
        for sid in created:
            with contextlib.suppress(Exception):
                await api.delete_strategy(sid)
        veupathdb_auth_token_ctx.reset(reset)


async def test_wdk_step_validations_fetched_live(
    require_wdk_creds: None, built_union: _Built
) -> None:
    del require_wdk_creds
    sync_state = ensure_sync_state(built_union.deps.strategy_session)
    validations = sync_state.step_validations
    assert set(validations) == {"kinase", "phosphatase", "combine"}
    assert all(isinstance(v, StepValidation) for v in validations.values())
    assert all(v.is_valid for v in validations.values())


async def test_wdk_step_validations_surfaced_in_persisted_ast(
    require_wdk_creds: None, built_union: _Built
) -> None:
    del require_wdk_creds
    async with built_union.session_maker() as session:
        conv = await session.get(Conversation, built_union.conv_id)
        assert conv is not None
        ast = StrategyAst.model_validate(conv.strategy_ast)
    assert ast.step_validations is not None, (
        "step validations were fetched from WDK but dropped at persistence"
    )
    assert set(ast.step_validations) == {"kinase", "phosphatase", "combine"}
    assert all(v.is_valid for v in ast.step_validations.values())

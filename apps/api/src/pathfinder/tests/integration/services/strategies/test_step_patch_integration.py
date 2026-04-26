from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.strategy_ast import StrategyAst
from pathfinder.integrations.veupathdb.wdk_models import (
    NewStepSpec,
    PatchStepSpec,
    WDKIdentifier,
    WDKSearchConfig,
    WDKStep,
)
from pathfinder.persistence.models import Conversation, User
from pathfinder.platform.security import create_user_token
from pathfinder.services.strategies import (
    plan_normalize,
    reconcile,
    step_patch,
    step_wdk_push,
)
from pathfinder.services.strategies.sync import SyncResult

pytestmark = pytest.mark.asyncio


@dataclass
class _CallRecord:
    name: str
    kwargs: dict[str, Any]


@dataclass
class CountingStrategyAPI:
    next_id: int = 1000
    calls: list[_CallRecord] = field(default_factory=list)
    pre_call_delay_seconds: float = 0.0

    def _alloc(self) -> int:
        self.next_id += 1
        return self.next_id

    async def _maybe_delay(self) -> None:
        if self.pre_call_delay_seconds > 0:
            await asyncio.sleep(self.pre_call_delay_seconds)

    async def create_step(
        self, spec: NewStepSpec, record_type: str, user_id: str | None = None
    ) -> WDKIdentifier:
        del user_id
        await self._maybe_delay()
        self.calls.append(
            _CallRecord(
                "create_step",
                {
                    "search_name": spec.search_name,
                    "parameters": dict(spec.search_config.parameters),
                    "record_type": record_type,
                },
            )
        )
        return WDKIdentifier(id=self._alloc())

    async def create_combined_step(
        self,
        primary_step_id: int,
        secondary_step_id: int,
        boolean_operator: str,
        record_type: str,
        **kwargs: Any,
    ) -> WDKIdentifier:
        del kwargs
        await self._maybe_delay()
        self.calls.append(
            _CallRecord(
                "create_combined_step",
                {
                    "primary_step_id": primary_step_id,
                    "secondary_step_id": secondary_step_id,
                    "boolean_operator": boolean_operator,
                    "record_type": record_type,
                },
            )
        )
        return WDKIdentifier(id=self._alloc())

    async def create_transform_step(
        self,
        spec: NewStepSpec,
        input_step_id: int,
        record_type: str = "transcript",
        *,
        user_id: str | None = None,
    ) -> WDKIdentifier:
        del user_id
        await self._maybe_delay()
        self.calls.append(
            _CallRecord(
                "create_transform_step",
                {
                    "search_name": spec.search_name,
                    "input_step_id": input_step_id,
                    "record_type": record_type,
                },
            )
        )
        return WDKIdentifier(id=self._alloc())

    async def update_step_search_config(
        self,
        step_id: int,
        search_config: WDKSearchConfig,
        record_type: str,
        search_name: str,
        *,
        user_id: str | None = None,
    ) -> None:
        del user_id
        await self._maybe_delay()
        self.calls.append(
            _CallRecord(
                "update_step_search_config",
                {
                    "step_id": step_id,
                    "search_name": search_name,
                    "record_type": record_type,
                    "parameters": dict(search_config.parameters),
                },
            )
        )

    async def update_step_properties(
        self,
        step_id: int,
        spec: PatchStepSpec,
        *,
        user_id: str | None = None,
    ) -> None:
        del user_id
        await self._maybe_delay()
        self.calls.append(
            _CallRecord(
                "update_step_properties",
                {"step_id": step_id, "custom_name": spec.custom_name},
            )
        )

    async def find_step(self, step_id: int, user_id: str | None = None) -> WDKStep:
        del user_id
        return WDKStep(
            id=step_id,
            search_name="GenesByTaxon",
            search_config=WDKSearchConfig(parameters={}),
        )



@pytest.fixture
def counting_api(monkeypatch: pytest.MonkeyPatch) -> CountingStrategyAPI:
    api = CountingStrategyAPI()
    monkeypatch.setattr(step_wdk_push, "get_strategy_api", lambda _site_id: api)

    async def _identity(
        *, strategy_ast: StrategyAst, site_id: str, **_kwargs: Any
    ) -> StrategyAst:
        del site_id
        return strategy_ast

    monkeypatch.setattr(plan_normalize, "canonicalize_strategy_ast_parameters", _identity)
    monkeypatch.setattr(step_patch, "canonicalize_strategy_ast_parameters", _identity)

    async def _noop_reconcile(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(step_patch, "reconcile_sync_state_with_wdk", _noop_reconcile)
    monkeypatch.setattr(reconcile, "reconcile_sync_state_with_wdk", _noop_reconcile)

    async def _fake_sync(
        *,
        graph: Any,
        sync_state: Any,
        site_id: str,
        strategy_name: str | None = None,
    ) -> SyncResult:
        del graph, sync_state, site_id, strategy_name
        return SyncResult(
            wdk_strategy_id=999,
            wdk_url="http://test",
            root_step_id=0,
            counts={},
            root_count=None,
            zero_step_ids=[],
            step_count=0,
        )

    monkeypatch.setattr(step_patch, "sync_strategy_for_site", _fake_sync)
    return api


@pytest.fixture
async def db_session(
    session_maker: async_sessionmaker[AsyncSession],
    db_cleaner: None,
) -> AsyncGenerator[AsyncSession]:
    del db_cleaner
    async with session_maker() as session:
        yield session


@pytest.fixture
async def seed_user(db_session: AsyncSession) -> User:
    user = User(id=uuid4())
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    return user


def _leaf(step_id: str, **params: Any) -> StrategyStepNode:
    return StrategyStepNode(
        search_name="GenesByTaxon",
        parameters=dict(params) if params else {"organism": ["Pf3D7"]},
        id=step_id,
    )


def _combine(
    step_id: str,
    primary: StrategyStepNode,
    secondary: StrategyStepNode,
    op: CombineOp = CombineOp.UNION,
) -> StrategyStepNode:
    return StrategyStepNode(
        search_name="__combine__",
        primary_input=primary,
        secondary_input=secondary,
        operator=op,
        id=step_id,
    )


def _seed_strategy_ast(wdk_step_ids: dict[str, int]) -> StrategyAst:
    a = _leaf("step_a", organism=["Pf3D7"])
    b = _leaf("step_b", organism=["PvP01"])
    c = _leaf("step_c", organism=["Pk"])
    inner = _combine("step_inner", a, b, op=CombineOp.UNION)
    outer = _combine("step_outer", inner, c, op=CombineOp.INTERSECT)
    return StrategyAst(record_type="transcript", root=outer, wdk_step_ids=wdk_step_ids)


async def _seed_conversation(
    db_session: AsyncSession, user: User, *, ast: StrategyAst
) -> UUID:
    conv = Conversation(
        id=uuid4(),
        user_id=user.id,
        site_id="plasmodb",
        name="Test strategy",
        wdk_strategy_id=555,
        strategy_ast=ast.model_dump(by_alias=True, exclude_none=True, mode="json"),
    )
    db_session.add(conv)
    await db_session.flush()
    await db_session.commit()
    return conv.id


@pytest.fixture
async def api_client(
    app: FastAPI,
    patch_app_db_engine: None,
    seed_user: User,
) -> AsyncGenerator[httpx.AsyncClient]:
    del patch_app_db_engine
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-Requested-With": "XMLHttpRequest"},
    ) as client:
        client.cookies.set("pathfinder-auth", create_user_token(seed_user.id))
        yield client


async def test_step_patch_endpoint_e2e_leaf_param_change(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    seed_user: User,
    counting_api: CountingStrategyAPI,
) -> None:
    wdk_ids = {
        "step_a": 100,
        "step_b": 101,
        "step_c": 102,
        "step_inner": 103,
        "step_outer": 104,
    }
    ast = _seed_strategy_ast(wdk_ids)
    conv_id = await _seed_conversation(db_session, seed_user, ast=ast)

    start = time.monotonic()
    resp = await api_client.patch(
        f"/api/v1/conversations/{conv_id}/steps/step_a",
        params={"siteId": "plasmodb"},
        json={"parameters": {"organism": ["Pf3D7", "Pf7G8"]}},
    )
    elapsed = time.monotonic() - start

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == "step_a"
    assert body["parameters"] == {"organism": ["Pf3D7", "Pf7G8"]}
    assert len(counting_api.calls) == 1
    assert counting_api.calls[0].name == "update_step_search_config"
    assert counting_api.calls[0].kwargs["step_id"] == 100
    assert counting_api.calls[0].kwargs["parameters"] == {
        "organism": '["Pf3D7", "Pf7G8"]'
    }
    assert elapsed < 1.0

    refetch = await api_client.get(f"/api/v1/conversations/{conv_id}")
    assert refetch.status_code == 200
    refetch_body = refetch.json()
    leaf_step = next(s for s in refetch_body["steps"] if s["id"] == "step_a")
    assert leaf_step["parameters"] == {"organism": ["Pf3D7", "Pf7G8"]}


async def test_step_patch_endpoint_e2e_combine_operator_change(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    seed_user: User,
    counting_api: CountingStrategyAPI,
) -> None:
    wdk_ids = {
        "step_a": 200,
        "step_b": 201,
        "step_c": 202,
        "step_inner": 203,
        "step_outer": 204,
    }
    ast = _seed_strategy_ast(wdk_ids)
    conv_id = await _seed_conversation(db_session, seed_user, ast=ast)

    resp = await api_client.patch(
        f"/api/v1/conversations/{conv_id}/steps/step_inner",
        params={"siteId": "plasmodb"},
        json={"operator": "INTERSECT"},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == "step_inner"
    assert body["operator"] == "INTERSECT"
    create_calls = [c for c in counting_api.calls if c.name == "create_combined_step"]
    assert len(create_calls) == 2
    assert create_calls[0].kwargs["boolean_operator"] == "INTERSECT"
    assert create_calls[1].kwargs["boolean_operator"] == "INTERSECT"

    refetch = await api_client.get(f"/api/v1/conversations/{conv_id}")
    assert refetch.status_code == 200
    refetch_body = refetch.json()
    inner_step = next(s for s in refetch_body["steps"] if s["id"] == "step_inner")
    assert inner_step["operator"] == "INTERSECT"


async def test_two_concurrent_patches_to_different_steps_both_succeed_no_clobber(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    seed_user: User,
    counting_api: CountingStrategyAPI,
) -> None:
    counting_api.pre_call_delay_seconds = 0.5
    wdk_ids = {
        "step_a": 300,
        "step_b": 301,
        "step_c": 302,
        "step_inner": 303,
        "step_outer": 304,
    }
    ast = _seed_strategy_ast(wdk_ids)
    conv_id = await _seed_conversation(db_session, seed_user, ast=ast)

    start = time.monotonic()
    patch_a, patch_b = await asyncio.gather(
        api_client.patch(
            f"/api/v1/conversations/{conv_id}/steps/step_a",
            params={"siteId": "plasmodb"},
            json={"parameters": {"organism": ["Pf3D7", "Pf7G8"]}},
        ),
        api_client.patch(
            f"/api/v1/conversations/{conv_id}/steps/step_b",
            params={"siteId": "plasmodb"},
            json={"parameters": {"organism": ["PvP01", "PvSal1"]}},
        ),
    )
    elapsed = time.monotonic() - start

    assert patch_a.status_code == 200, patch_a.text
    assert patch_b.status_code == 200, patch_b.text
    assert patch_a.json()["parameters"] == {"organism": ["Pf3D7", "Pf7G8"]}
    assert patch_b.json()["parameters"] == {"organism": ["PvP01", "PvSal1"]}
    assert elapsed < 1.5
    assert len(counting_api.calls) == 2
    assert {c.kwargs["step_id"] for c in counting_api.calls} == {300, 301}

    refetch = await api_client.get(f"/api/v1/conversations/{conv_id}")
    assert refetch.status_code == 200
    body = refetch.json()
    leaf_a = next(s for s in body["steps"] if s["id"] == "step_a")
    leaf_b = next(s for s in body["steps"] if s["id"] == "step_b")
    assert leaf_a["parameters"] == {"organism": ["Pf3D7", "Pf7G8"]}
    assert leaf_b["parameters"] == {"organism": ["PvP01", "PvSal1"]}

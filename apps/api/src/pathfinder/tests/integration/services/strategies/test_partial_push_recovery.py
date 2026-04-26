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
    WDKStepTree,
    WDKStrategyDetails,
)
from pathfinder.persistence.models import Conversation, User
from pathfinder.platform.errors import PartialPushError, WDKError
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
    fail_on_search_names: set[str] = field(default_factory=set)
    pre_call_delay_seconds: float = 0.0
    live_step_tree: WDKStepTree | None = None
    sync_call_count: int = 0

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
        if spec.search_name in self.fail_on_search_names:
            msg = f"synthetic failure for {spec.search_name}"
            raise WDKError(msg)
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
        del user_id, record_type, search_config
        await self._maybe_delay()
        self.calls.append(
            _CallRecord(
                "update_step_search_config",
                {"step_id": step_id, "search_name": search_name},
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

    async def get_strategy(
        self, strategy_id: int, user_id: str | None = None
    ) -> WDKStrategyDetails:
        del user_id
        self.calls.append(_CallRecord("get_strategy", {"strategy_id": strategy_id}))
        if self.live_step_tree is None:
            return WDKStrategyDetails(
                strategy_id=strategy_id,
                name="t",
                root_step_id=0,
                step_tree=WDKStepTree(step_id=0),
            )
        return WDKStrategyDetails(
            strategy_id=strategy_id,
            name="t",
            root_step_id=self.live_step_tree.step_id,
            step_tree=self.live_step_tree,
        )


@pytest.fixture
def counting_api(monkeypatch: pytest.MonkeyPatch) -> CountingStrategyAPI:
    api = CountingStrategyAPI()
    monkeypatch.setattr(step_wdk_push, "get_strategy_api", lambda _site_id: api)
    monkeypatch.setattr(reconcile, "get_strategy_api", lambda _site_id: api)

    async def _identity(
        *, strategy_ast: StrategyAst, site_id: str, **_kwargs: Any
    ) -> StrategyAst:
        del site_id
        return strategy_ast

    monkeypatch.setattr(plan_normalize, "canonicalize_strategy_ast_parameters", _identity)
    monkeypatch.setattr(step_patch, "canonicalize_strategy_ast_parameters", _identity)

    async def _fake_sync(
        *, graph: Any, sync_state: Any, site_id: str, strategy_name: str | None = None,
    ) -> SyncResult:
        del graph, sync_state, site_id, strategy_name
        api.sync_call_count += 1
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


def _leaf(step_id: str, search: str = "GenesByTaxon", **params: Any) -> StrategyStepNode:
    return StrategyStepNode(
        search_name=search,
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


async def _seed_conversation(
    db_session: AsyncSession, user: User, *, ast: StrategyAst,
    wdk_strategy_id: int | None = 555,
) -> UUID:
    conv = Conversation(
        id=uuid4(),
        user_id=user.id,
        site_id="plasmodb",
        name="Test strategy",
        wdk_strategy_id=wdk_strategy_id,
        strategy_ast=ast.model_dump(by_alias=True, exclude_none=True, mode="json"),
    )
    db_session.add(conv)
    await db_session.flush()
    await db_session.commit()
    return conv.id


async def test_partial_push_persists_succeeded_wdk_ids_skips_sync(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    seed_user: User,
    counting_api: CountingStrategyAPI,
) -> None:
    counting_api.fail_on_search_names = {"SearchC"}

    a = _leaf("step_a", "SearchA", organism=["Pf3D7"])
    b = _leaf("step_b", "SearchB", organism=["PvP01"])
    c = _leaf("step_c", "SearchC", organism=["Pk"])
    inner = _combine("step_inner", a, b, op=CombineOp.UNION)
    outer = _combine("step_outer", inner, c, op=CombineOp.INTERSECT)
    seeded_ast = StrategyAst(record_type="transcript", root=outer)
    conv_id = await _seed_conversation(
        db_session, seed_user, ast=seeded_ast, wdk_strategy_id=None,
    )

    resp = await api_client.patch(
        f"/api/v1/conversations/{conv_id}/steps/step_a",
        params={"siteId": "plasmodb"},
        json={"display_name": "Force-recompute"},
    )

    assert resp.status_code == 502, resp.text
    body = resp.json()
    assert body["code"] == "WDK_ERROR"
    assert body["title"] == "Partial WDK push"
    assert "step_c" in body["detail"]

    assert counting_api.sync_call_count == 0

    refreshed = await db_session.get(Conversation, conv_id)
    assert refreshed is not None
    await db_session.refresh(refreshed)
    persisted_ast = StrategyAst.model_validate(refreshed.strategy_ast)
    persisted_ids = persisted_ast.wdk_step_ids or {}
    assert "step_a" in persisted_ids
    assert "step_b" in persisted_ids
    assert "step_inner" in persisted_ids
    assert "step_c" not in persisted_ids
    assert "step_outer" not in persisted_ids


async def test_retry_after_partial_failure_does_not_duplicate(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    seed_user: User,
    counting_api: CountingStrategyAPI,
) -> None:
    counting_api.fail_on_search_names = {"SearchC"}

    a = _leaf("step_a", "SearchA", organism=["Pf3D7"])
    b = _leaf("step_b", "SearchB", organism=["PvP01"])
    c = _leaf("step_c", "SearchC", organism=["Pk"])
    inner = _combine("step_inner", a, b, op=CombineOp.UNION)
    outer = _combine("step_outer", inner, c, op=CombineOp.INTERSECT)
    initial_ast = StrategyAst(record_type="transcript", root=outer)

    conv_id = await _seed_conversation(
        db_session, seed_user, ast=initial_ast, wdk_strategy_id=None,
    )

    resp1 = await api_client.patch(
        f"/api/v1/conversations/{conv_id}/steps/step_a",
        params={"siteId": "plasmodb"},
        json={"display_name": "Force-1"},
    )
    assert resp1.status_code == 502, resp1.text

    create_step_calls_first = [c for c in counting_api.calls if c.name == "create_step"]
    create_combined_first = [c for c in counting_api.calls if c.name == "create_combined_step"]
    assert {c.kwargs["search_name"] for c in create_step_calls_first} == {
        "SearchA", "SearchB", "SearchC",
    }
    assert len(create_combined_first) == 1
    assert create_combined_first[0].kwargs["boolean_operator"] == "UNION"

    refetched = await db_session.get(Conversation, conv_id)
    assert refetched is not None
    await db_session.refresh(refetched)
    persisted_ast = StrategyAst.model_validate(refetched.strategy_ast)
    persisted_ids = persisted_ast.wdk_step_ids or {}
    assert "step_a" in persisted_ids
    assert "step_b" in persisted_ids
    assert "step_inner" in persisted_ids
    assert "step_c" not in persisted_ids
    assert "step_outer" not in persisted_ids

    a_wdk_id_after_partial = persisted_ids["step_a"]
    b_wdk_id_after_partial = persisted_ids["step_b"]
    inner_wdk_id_after_partial = persisted_ids["step_inner"]

    counting_api.fail_on_search_names = set()
    counting_api.calls.clear()
    assert counting_api.sync_call_count == 0

    resp2 = await api_client.patch(
        f"/api/v1/conversations/{conv_id}/steps/step_a",
        params={"siteId": "plasmodb"},
        json={"display_name": "Force-2"},
    )
    assert resp2.status_code == 200, resp2.text

    create_step_calls_retry = [c for c in counting_api.calls if c.name == "create_step"]
    assert len(create_step_calls_retry) == 1
    assert create_step_calls_retry[0].kwargs["search_name"] == "SearchC"

    create_combined_retry = [c for c in counting_api.calls if c.name == "create_combined_step"]
    assert len(create_combined_retry) == 1
    assert create_combined_retry[0].kwargs["boolean_operator"] == "INTERSECT"

    final = await db_session.get(Conversation, conv_id)
    assert final is not None
    await db_session.refresh(final)
    final_ast = StrategyAst.model_validate(final.strategy_ast)
    final_ids = final_ast.wdk_step_ids or {}
    assert set(final_ids.keys()) >= {
        "step_a", "step_b", "step_c", "step_inner", "step_outer",
    }
    assert final_ids["step_a"] == a_wdk_id_after_partial
    assert final_ids["step_b"] == b_wdk_id_after_partial
    assert final_ids["step_inner"] == inner_wdk_id_after_partial
    assert counting_api.sync_call_count == 1


async def test_concurrent_agent_and_user_patch_no_clobber(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    seed_user: User,
    counting_api: CountingStrategyAPI,
) -> None:
    counting_api.pre_call_delay_seconds = 0.3
    counting_api.live_step_tree = WDKStepTree(
        step_id=702,
        primary_input=WDKStepTree(step_id=700),
        secondary_input=WDKStepTree(step_id=701),
    )
    a = _leaf("step_a", "SearchA", organism=["Pf3D7"])
    b = _leaf("step_b", "SearchB", organism=["PvP01"])
    inner = _combine("step_inner", a, b, op=CombineOp.UNION)
    seeded_ast = StrategyAst(
        record_type="transcript",
        root=inner,
        wdk_step_ids={"step_a": 700, "step_b": 701, "step_inner": 702},
    )
    conv_id = await _seed_conversation(db_session, seed_user, ast=seeded_ast)

    start = time.monotonic()
    resp_a, resp_b = await asyncio.gather(
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

    assert resp_a.status_code == 200, resp_a.text
    assert resp_b.status_code == 200, resp_b.text
    assert resp_a.json()["parameters"] == {"organism": ["Pf3D7", "Pf7G8"]}
    assert resp_b.json()["parameters"] == {"organism": ["PvP01", "PvSal1"]}
    assert elapsed < 1.5

    update_calls = [c for c in counting_api.calls if c.name == "update_step_search_config"]
    assert {c.kwargs["step_id"] for c in update_calls} == {700, 701}

    final = await db_session.get(Conversation, conv_id)
    assert final is not None
    await db_session.refresh(final)
    final_ast = StrategyAst.model_validate(final.strategy_ast)
    assert final_ast.wdk_step_ids == {"step_a": 700, "step_b": 701, "step_inner": 702}


async def test_reconciliation_drops_orphaned_wdk_ids(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    seed_user: User,
    counting_api: CountingStrategyAPI,
) -> None:
    a = _leaf("step_a", "SearchA", organism=["Pf3D7"])
    b = _leaf("step_b", "SearchB", organism=["PvP01"])
    inner = _combine("step_inner", a, b, op=CombineOp.UNION)
    seeded_ast = StrategyAst(
        record_type="transcript",
        root=inner,
        wdk_step_ids={"step_a": 100, "step_b": 999, "step_inner": 800},
    )
    conv_id = await _seed_conversation(db_session, seed_user, ast=seeded_ast)

    counting_api.live_step_tree = WDKStepTree(
        step_id=800,
        primary_input=WDKStepTree(step_id=100),
        secondary_input=WDKStepTree(step_id=102),
    )

    resp = await api_client.patch(
        f"/api/v1/conversations/{conv_id}/steps/step_b",
        params={"siteId": "plasmodb"},
        json={"display_name": "Force-recompute"},
    )

    assert resp.status_code == 200, resp.text

    create_step_calls = [c for c in counting_api.calls if c.name == "create_step"]
    assert len(create_step_calls) == 1
    assert create_step_calls[0].kwargs["search_name"] == "SearchB"

    create_combined_calls = [
        c for c in counting_api.calls if c.name == "create_combined_step"
    ]
    assert len(create_combined_calls) == 1


async def test_partial_push_error_serializes_with_succeeded_failed_lists() -> None:
    err = PartialPushError(
        succeeded_step_ids=["a", "b"],
        failed_step_ids=["c"],
    )
    assert err.status == 502
    assert err.succeeded_step_ids == ["a", "b"]
    assert err.failed_step_ids == ["c"]
    assert "['c']" in str(err)

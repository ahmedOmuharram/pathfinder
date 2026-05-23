"""Integration test for ``apply_and_commit`` (the unified verb pipeline)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.domain.parameters.values import MultiPickValue
from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.domain.strategy.operations import (
    DeleteResolution,
    DeleteStepOp,
    UpdateStepMetaOp,
)
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.session import StrategyGraph, StrategySession
from pathfinder.domain.strategy.strategy_ast import StrategyAst
from pathfinder.integrations.veupathdb.wdk_models import (
    NewStepSpec,
    PatchStepSpec,
    WDKIdentifier,
    WDKSearchConfig,
    WDKStep,
)
from pathfinder.persistence.models import Conversation, User
from pathfinder.persistence.repositories.conversation import ConversationRepository
from pathfinder.services.strategies import (
    commit as commit_module,
)
from pathfinder.services.strategies import (
    step_wdk_push,
)
from pathfinder.services.strategies import (
    sync as sync_module,
)
from pathfinder.services.strategies.commit import apply_and_commit
from pathfinder.services.strategies.sync import SyncResult
from pathfinder.services.strategies.sync_state import WDKSyncState

pytestmark = pytest.mark.asyncio


@dataclass
class _Call:
    name: str
    kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass
class _CountingAPI:
    calls: list[_Call] = field(default_factory=list)
    next_id: int = 9000

    def _alloc(self) -> int:
        self.next_id += 1
        return self.next_id

    async def delete_step(self, step_id: int, *, user_id: str | None = None) -> None:
        del user_id
        self.calls.append(_Call("delete_step", {"step_id": step_id}))

    async def create_step(
        self, spec: NewStepSpec, record_type: str, user_id: str | None = None,
    ) -> WDKIdentifier:
        del user_id
        self.calls.append(
            _Call("create_step", {"search_name": spec.search_name, "record_type": record_type}),
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
        self.calls.append(
            _Call(
                "create_combined_step",
                {
                    "primary_step_id": primary_step_id,
                    "secondary_step_id": secondary_step_id,
                    "boolean_operator": boolean_operator,
                    "record_type": record_type,
                },
            ),
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
        self.calls.append(
            _Call(
                "create_transform_step",
                {
                    "search_name": spec.search_name,
                    "input_step_id": input_step_id,
                    "record_type": record_type,
                },
            ),
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
        self.calls.append(
            _Call(
                "update_step_search_config",
                {
                    "step_id": step_id,
                    "search_name": search_name,
                    "record_type": record_type,
                    "parameters": dict(search_config.parameters),
                },
            ),
        )

    async def update_step_properties(
        self,
        step_id: int,
        spec: PatchStepSpec,
        *,
        user_id: str | None = None,
    ) -> None:
        del user_id
        self.calls.append(_Call("update_step_properties", {"step_id": step_id, "spec": spec}))

    async def find_step(self, step_id: int, user_id: str | None = None) -> WDKStep:
        del user_id
        return WDKStep(
            id=step_id,
            search_name="GenesByTaxon",
            search_config=WDKSearchConfig(parameters={}),
        )


@pytest.fixture
def stub_api(monkeypatch: pytest.MonkeyPatch) -> _CountingAPI:
    api = _CountingAPI()
    monkeypatch.setattr(commit_module, "get_strategy_api", lambda _site_id: api)
    monkeypatch.setattr(step_wdk_push, "get_strategy_api", lambda _site_id: api)
    monkeypatch.setattr(sync_module, "get_strategy_api", lambda _site_id: api)

    async def _noop_reconcile(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(commit_module, "reconcile_sync_state_with_wdk", _noop_reconcile)

    async def _fake_sync(
        *,
        graph: Any,
        sync_state: Any,
        site_id: str,
        strategy_name: str | None = None,
    ) -> SyncResult:
        del graph, sync_state, site_id, strategy_name
        return SyncResult(
            wdk_strategy_id=42,
            wdk_url="http://test",
            root_step_id=0,
            counts={},
            root_count=None,
            zero_step_ids=[],
            step_count=0,
        )

    monkeypatch.setattr(commit_module, "sync_strategy_for_site", _fake_sync)
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


def _leaf(id_: str) -> StrategyStepNode:
    return StrategyStepNode(id=id_, search_name="GenesByTaxon", parameters={"organism": MultiPickValue(values=["Pf3D7"])})


def _combine(
    id_: str, p: StrategyStepNode, s: StrategyStepNode, op: CombineOp = CombineOp.INTERSECT,
) -> StrategyStepNode:
    return StrategyStepNode(
        id=id_,
        search_name="__combine__",
        primary_input=p,
        secondary_input=s,
        operator=op,
    )


async def _seed_conversation(
    db_session: AsyncSession,
    user: User,
    *,
    root: StrategyStepNode,
    wdk_step_ids: dict[str, int],
) -> UUID:
    ast = StrategyAst(
        record_type="transcript", root=root, wdk_step_ids=wdk_step_ids,
    )
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


def _build_deps(
    *,
    conv_id: UUID,
    root: StrategyStepNode,
    wdk_step_ids: dict[str, int],
    db_session_factory: Any,
) -> AgentDeps:
    session = StrategySession(site_id="plasmodb")
    graph = StrategyGraph(graph_id=str(conv_id), name="Test strategy", site_id="plasmodb")
    graph.record_type = "transcript"
    stack = [root]
    while stack:
        node = stack.pop()
        graph.steps[node.id] = node
        if node.primary_input is not None:
            stack.append(node.primary_input)
        if node.secondary_input is not None:
            stack.append(node.secondary_input)
    graph.recompute_roots()
    session.graph = graph
    session.sync_state = WDKSyncState(
        wdk_step_ids=dict(wdk_step_ids), wdk_strategy_id=555,
    )
    return AgentDeps(
        site_id="plasmodb",
        strategy_session=session,
        conversation_id=conv_id,
        db_session_factory=db_session_factory,
    )


async def test_delete_collapse_combine_drops_wdk_steps_and_persists_ast(
    db_session: AsyncSession,
    session_maker: async_sessionmaker[AsyncSession],
    seed_user: User,
    stub_api: _CountingAPI,
) -> None:
    a = _leaf("step_a")
    b = _leaf("step_b")
    c = _combine("step_c", a, b)
    wdk_ids = {"step_a": 100, "step_b": 200, "step_c": 300}
    conv_id = await _seed_conversation(
        db_session, seed_user, root=c, wdk_step_ids=wdk_ids,
    )
    deps = _build_deps(
        conv_id=conv_id, root=c, wdk_step_ids=wdk_ids, db_session_factory=session_maker,
    )

    result = await apply_and_commit(
        deps=deps,
        op=DeleteStepOp(
            step_id="step_a", resolution=DeleteResolution.COLLAPSE_COMBINE,
        ),
    )

    assert sorted(result.dropped_step_ids) == ["step_a", "step_c"]
    deleted_wdk = {c.kwargs["step_id"] for c in stub_api.calls if c.name == "delete_step"}
    assert deleted_wdk == {100, 300}

    async with session_maker() as fresh:
        repo = ConversationRepository(fresh)
        refetched = await repo.get_by_id(conv_id)
        assert refetched is not None
        ast = StrategyAst.model_validate(refetched.strategy_ast)
        assert ast.root.id == "step_b"
        assert ast.root.primary_input is None
        assert ast.root.secondary_input is None


async def test_update_step_meta_persists_without_wdk_delete(
    db_session: AsyncSession,
    session_maker: async_sessionmaker[AsyncSession],
    seed_user: User,
    stub_api: _CountingAPI,
) -> None:
    a = _leaf("step_a")
    conv_id = await _seed_conversation(
        db_session, seed_user, root=a, wdk_step_ids={"step_a": 100},
    )
    deps = _build_deps(
        conv_id=conv_id,
        root=a,
        wdk_step_ids={"step_a": 100},
        db_session_factory=session_maker,
    )

    await apply_and_commit(
        deps=deps,
        op=UpdateStepMetaOp(step_id="step_a", display_name="Renamed step"),
    )

    deletes = [c for c in stub_api.calls if c.name == "delete_step"]
    assert deletes == []

    async with session_maker() as fresh:
        repo = ConversationRepository(fresh)
        refetched = await repo.get_by_id(conv_id)
        assert refetched is not None
        ast = StrategyAst.model_validate(refetched.strategy_ast)
        assert ast.root.display_name == "Renamed step"

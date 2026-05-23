from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import pytest
from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.standalone import strategy as strategy_module
from pathfinder.ai.tools.standalone.strategy import (
    delete_step,
    insert_saved_strategy,
    replace_subtree,
    update_combine_operator,
    update_leaf_params,
    update_step_metadata,
)
from pathfinder.domain.parameters.values import MultiPickValue
from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.domain.strategy.operations import DeleteResolution
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.session import StrategyGraph, StrategySession
from pathfinder.integrations.veupathdb.wdk_models import (
    NewStepSpec,
    PatchStepSpec,
    WDKIdentifier,
    WDKSearchConfig,
    WDKStep,
)
from pathfinder.platform.errors import ValidationError
from pathfinder.platform.tool_errors import ToolErrorPayload
from pathfinder.services.strategies import (
    commit as commit_module,
)
from pathfinder.services.strategies import (
    step_wdk_push,
)
from pathfinder.services.strategies import (
    sync as sync_module,
)
from pathfinder.services.strategies.sync import SyncResult
from pathfinder.services.strategies.sync_state import WDKSyncState


@dataclass
class _Call:
    name: str
    kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass
class _StubAPI:
    calls: list[_Call] = field(default_factory=list)
    next_id: int = 9000

    def _alloc(self) -> int:
        self.next_id += 1
        return self.next_id

    async def delete_step(self, step_id: int, *, user_id: str | None = None) -> None:
        del user_id
        self.calls.append(_Call("delete_step", {"step_id": step_id}))

    async def create_step(
        self, spec: NewStepSpec, record_type: str, user_id: str | None = None
    ) -> WDKIdentifier:
        del user_id
        self.calls.append(
            _Call(
                "create_step",
                {"search_name": spec.search_name, "record_type": record_type},
            ),
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
def stub_api(monkeypatch: pytest.MonkeyPatch) -> _StubAPI:
    api = _StubAPI()
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
            wdk_url="http://example",
            root_step_id=0,
            counts={},
            root_count=None,
            zero_step_ids=[],
            step_count=0,
        )

    monkeypatch.setattr(commit_module, "sync_strategy_for_site", _fake_sync)

    async def _noop_persist(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(
        commit_module, "persist_strategy_ast_to_conversation", _noop_persist,
    )

    async def _noop_validate(*_args: Any, **kwargs: Any) -> dict[str, object]:
        return dict(kwargs.get("parameters") or {})

    monkeypatch.setattr(strategy_module, "validate_parameters", _noop_validate)
    return api


def _leaf(id_: str, params: dict[str, Any] | None = None) -> StrategyStepNode:
    return StrategyStepNode(
        id=id_, search_name="GenesByTaxon", parameters=params or {},
    )


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


def _seed(root: StrategyStepNode, wdk_step_ids: dict[str, int]) -> AgentDeps:
    session = StrategySession(site_id="plasmodb")
    graph = StrategyGraph(graph_id="g1", name="Test", site_id="plasmodb")
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
        wdk_step_ids=dict(wdk_step_ids), wdk_strategy_id=42,
    )
    return AgentDeps(
        site_id="plasmodb",
        strategy_session=session,
        conversation_id=uuid4(),
    )


def _ctx(deps: AgentDeps) -> RunContext[AgentDeps]:
    return RunContext(deps=deps, model=TestModel(), usage=RunUsage(), messages=[])


# --- delete_step ---------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_step_collapse_combine(stub_api: _StubAPI) -> None:
    a = _leaf("A")
    b = _leaf("B")
    c = _combine("C", a, b)
    deps = _seed(c, wdk_step_ids={"A": 100, "B": 200, "C": 300})

    res = await delete_step(_ctx(deps), "A")

    assert hasattr(res, "return_value")
    payload = res.return_value
    assert payload["ok"] is True
    assert sorted(payload["deleted"]) == ["A", "C"]
    deleted_wdk = {c.kwargs["step_id"] for c in stub_api.calls if c.name == "delete_step"}
    assert deleted_wdk == {100, 300}


@pytest.mark.asyncio
async def test_delete_step_unknown_id_raises_model_retry(stub_api: _StubAPI) -> None:
    del stub_api
    a = _leaf("A")
    deps = _seed(a, wdk_step_ids={"A": 100})
    with pytest.raises(ModelRetry):
        await delete_step(_ctx(deps), "missing")


@pytest.mark.asyncio
async def test_delete_step_promote_primary(stub_api: _StubAPI) -> None:
    a = _leaf("a")
    b = _leaf("b")
    c = _combine("c", a, b)
    deps = _seed(c, wdk_step_ids={"a": 100, "b": 200, "c": 300})

    res = await delete_step(
        _ctx(deps), "c", resolution=DeleteResolution.PROMOTE_PRIMARY,
    )

    payload = res.return_value
    assert sorted(payload["deleted"]) == ["b", "c"]
    deleted_wdk = {c.kwargs["step_id"] for c in stub_api.calls if c.name == "delete_step"}
    assert deleted_wdk == {200, 300}


# --- update_leaf_params --------------------------------------------------


@pytest.mark.asyncio
async def test_update_leaf_params_happy(stub_api: _StubAPI) -> None:
    a = _leaf(
        "a",
        params={"organism": MultiPickValue(values=["Pf3D7"])},
    )
    deps = _seed(a, wdk_step_ids={"a": 100})

    res = await update_leaf_params(
        _ctx(deps), "a",
        {"organism": MultiPickValue(values=["Pf3D7", "Pf7G8"])},
    )

    assert hasattr(res, "return_value")
    graph = deps.strategy_session.graph
    assert graph is not None
    assert graph.steps["a"].parameters == {
        "organism": MultiPickValue(values=["Pf3D7", "Pf7G8"]),
    }
    patch_calls = [c for c in stub_api.calls if c.name == "update_step_search_config"]
    assert len(patch_calls) >= 1, f"calls: {[c.name for c in stub_api.calls]}"
    assert patch_calls[0].kwargs["step_id"] == 100


@pytest.mark.asyncio
async def test_update_leaf_params_rejects_combine(stub_api: _StubAPI) -> None:
    del stub_api
    a = _leaf("a")
    b = _leaf("b")
    c = _combine("c", a, b)
    deps = _seed(c, wdk_step_ids={"a": 100, "b": 200, "c": 300})

    with pytest.raises(ModelRetry):
        await update_leaf_params(_ctx(deps), "c", {})


@pytest.mark.asyncio
async def test_update_leaf_params_validation_failure_raises_model_retry(
    stub_api: _StubAPI, monkeypatch: pytest.MonkeyPatch,
) -> None:
    del stub_api

    a = _leaf(
        "a",
        params={"organism": MultiPickValue(values=["Pf3D7"])},
    )
    deps = _seed(a, wdk_step_ids={"a": 100})

    async def _raising_validate(*_args: Any, **_kwargs: Any) -> dict[str, object]:
        raise ValidationError(
            title="Invalid parameter value",
            detail="Parameter 'organism' does not accept 'NotARealOrganism'.",
            errors=[
                {
                    "param": "organism",
                    "value": "NotARealOrganism",
                    "validOptions": ["Pf3D7", "PvP01"],
                },
            ],
        )

    monkeypatch.setattr(strategy_module, "validate_parameters", _raising_validate)

    with pytest.raises(ModelRetry) as excinfo:
        await update_leaf_params(
            _ctx(deps), "a", {"organism": ["NotARealOrganism"]},
        )

    msg = str(excinfo.value)
    assert "Invalid parameter value" in msg
    assert "validOptions" in msg
    assert "NotARealOrganism" in msg


# --- update_combine_operator ---------------------------------------------


@pytest.mark.asyncio
async def test_update_combine_operator_happy(stub_api: _StubAPI) -> None:
    del stub_api
    a = _leaf("a")
    b = _leaf("b")
    c = _combine("c", a, b, op=CombineOp.INTERSECT)
    deps = _seed(c, wdk_step_ids={"a": 100, "b": 200, "c": 300})

    res = await update_combine_operator(_ctx(deps), "c", CombineOp.UNION)

    assert hasattr(res, "return_value")
    assert deps.strategy_session.graph is not None
    assert deps.strategy_session.graph.steps["c"].operator == CombineOp.UNION


@pytest.mark.asyncio
async def test_update_combine_operator_rejects_leaf(stub_api: _StubAPI) -> None:
    del stub_api
    a = _leaf("a")
    deps = _seed(a, wdk_step_ids={"a": 100})

    with pytest.raises(ModelRetry):
        await update_combine_operator(_ctx(deps), "a", CombineOp.INTERSECT)


@pytest.mark.asyncio
async def test_update_combine_operator_colocate_requires_params(
    stub_api: _StubAPI,
) -> None:
    del stub_api
    a = _leaf("a")
    b = _leaf("b")
    c = _combine("c", a, b)
    deps = _seed(c, wdk_step_ids={"a": 100, "b": 200, "c": 300})

    with pytest.raises(ModelRetry):
        await update_combine_operator(
            _ctx(deps), "c", CombineOp.COLOCATE, colocation_params=None,
        )


# --- update_step_metadata ------------------------------------------------


@pytest.mark.asyncio
async def test_update_step_metadata_renames(stub_api: _StubAPI) -> None:
    a = _leaf("a")
    deps = _seed(a, wdk_step_ids={"a": 100})

    res = await update_step_metadata(_ctx(deps), "a", "renamed")

    assert hasattr(res, "return_value")
    assert deps.strategy_session.graph is not None
    assert deps.strategy_session.graph.steps["a"].display_name == "renamed"
    deletes = [c for c in stub_api.calls if c.name == "delete_step"]
    assert deletes == []


# --- replace_subtree -----------------------------------------------------


@pytest.mark.asyncio
async def test_replace_subtree_drops_old_creates_new(stub_api: _StubAPI) -> None:
    a = _leaf("a")
    b = _leaf("b")
    c = _combine("c", a, b)
    deps = _seed(c, wdk_step_ids={"a": 100, "b": 200, "c": 300})

    new_a = _leaf("new_a")
    res = await replace_subtree(_ctx(deps), "a", new_a)

    assert hasattr(res, "return_value")
    payload = res.return_value
    assert payload["replacedStepId"] == "a"
    assert "a" in payload["droppedStepIds"]
    deleted_wdk = {c.kwargs["step_id"] for c in stub_api.calls if c.name == "delete_step"}
    assert 100 in deleted_wdk
    create_calls = [c for c in stub_api.calls if c.name == "create_step"]
    assert any(c.kwargs.get("search_name") == "GenesByTaxon" for c in create_calls)


@pytest.mark.asyncio
async def test_replace_subtree_unknown_id_raises_model_retry(
    stub_api: _StubAPI,
) -> None:
    del stub_api
    a = _leaf("a")
    deps = _seed(a, wdk_step_ids={"a": 100})

    with pytest.raises(ModelRetry):
        await replace_subtree(_ctx(deps), "missing", _leaf("new"))


# --- insert_saved_strategy guards ----------------------------------------


@pytest.mark.asyncio
async def test_insert_saved_strategy_requires_persistent_context(
    stub_api: _StubAPI,
) -> None:
    del stub_api
    a = _leaf("a")
    session = StrategySession(site_id="plasmodb")
    graph = StrategyGraph(graph_id="g1", name="Test", site_id="plasmodb")
    graph.record_type = "transcript"
    graph.steps[a.id] = a
    graph.recompute_roots()
    session.graph = graph
    session.sync_state = WDKSyncState(wdk_step_ids={"a": 100})
    deps = AgentDeps(
        site_id="plasmodb",
        strategy_session=session,
        conversation_id=None,
        db_session_factory=None,
    )

    res = await insert_saved_strategy(_ctx(deps), "a", 12345)
    assert isinstance(res, ToolErrorPayload)

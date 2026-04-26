from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from pathfinder.domain.strategy.ast import StrategyStepNode, walk_step_tree
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.session import StrategyGraph
from pathfinder.domain.strategy.strategy_ast import StrategyAst
from pathfinder.integrations.veupathdb.wdk_models import (
    NewStepSpec,
    PatchStepSpec,
    WDKIdentifier,
    WDKSearchConfig,
    WDKStep,
)
from pathfinder.services.strategies import step_wdk_push
from pathfinder.services.strategies.step_push_planner import (
    plan_step_pushes,
)
from pathfinder.services.strategies.step_wdk_push import push_steps_with_plan
from pathfinder.services.strategies.sync_state import WDKSyncState


@dataclass
class _CallRecord:
    name: str
    kwargs: dict[str, Any]


@dataclass
class CountingStrategyAPI:
    next_id: int = 1000
    calls: list[_CallRecord] = field(default_factory=list)
    boolean_param_left: str = "bq_left_op"
    boolean_param_right: str = "bq_right_op"
    boolean_param_op: str = "bq_operator"

    def _alloc(self) -> int:
        self.next_id += 1
        return self.next_id

    async def create_step(
        self, spec: NewStepSpec, record_type: str, user_id: str | None = None
    ) -> WDKIdentifier:
        del user_id
        self.calls.append(
            _CallRecord(
                "create_step",
                {
                    "search_name": spec.search_name,
                    "parameters": dict(spec.search_config.parameters),
                    "custom_name": spec.custom_name,
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
        spec_overrides = kwargs.get("spec_overrides")
        self.calls.append(
            _CallRecord(
                "create_combined_step",
                {
                    "primary_step_id": primary_step_id,
                    "secondary_step_id": secondary_step_id,
                    "boolean_operator": boolean_operator,
                    "record_type": record_type,
                    "custom_name": spec_overrides.custom_name if spec_overrides else None,
                    "wdk_weight": kwargs.get("wdk_weight"),
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
        self.calls.append(
            _CallRecord(
                "create_transform_step",
                {
                    "search_name": spec.search_name,
                    "input_step_id": input_step_id,
                    "record_type": record_type,
                    "parameters": dict(spec.search_config.parameters),
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
    return api


def _populate_graph_from_ast(graph: StrategyGraph, ast: StrategyAst) -> None:
    for step in walk_step_tree(ast.root):
        graph.steps[step.id] = step
    graph.record_type = ast.record_type
    graph.recompute_roots()


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


def _ast(root: StrategyStepNode) -> StrategyAst:
    return StrategyAst(record_type="transcript", root=root)


async def _initial_push(
    graph: StrategyGraph, sync_state: WDKSyncState, ast: StrategyAst
) -> None:
    initial_plan = plan_step_pushes(
        old_ast=None, new_ast=ast, existing_wdk_ids={},
    )
    await push_steps_with_plan(graph, sync_state, "plasmodb", initial_plan)


async def test_push_unchanged_strategy_makes_zero_wdk_calls(
    counting_api: CountingStrategyAPI,
) -> None:
    a = _leaf("a", organism=["Pf3D7"])
    b = _leaf("b", organism=["PvP01"])
    c = _leaf("c", organism=["Pk"])
    inner = _combine("inner", a, b, op=CombineOp.UNION)
    outer = _combine("outer", inner, c, op=CombineOp.INTERSECT)
    ast = _ast(outer)

    graph = StrategyGraph("g1", "test", "plasmodb")
    sync_state = WDKSyncState()
    _populate_graph_from_ast(graph, ast)

    await _initial_push(graph, sync_state, ast)
    counting_api.calls.clear()

    plan = plan_step_pushes(old_ast=ast, new_ast=ast, existing_wdk_ids=sync_state.wdk_step_ids)
    outcome = await push_steps_with_plan(graph, sync_state, "plasmodb", plan)

    assert outcome.failed == []
    assert counting_api.calls == []


async def test_push_single_leaf_param_change_makes_one_patch_call(
    counting_api: CountingStrategyAPI,
) -> None:
    a = _leaf("a", organism=["Pf3D7"])
    b = _leaf("b", organism=["PvP01"])
    c = _leaf("c", organism=["Pk"])
    inner = _combine("inner", a, b, op=CombineOp.UNION)
    outer = _combine("outer", inner, c, op=CombineOp.INTERSECT)
    old_ast = _ast(outer)

    graph = StrategyGraph("g1", "test", "plasmodb")
    sync_state = WDKSyncState()
    _populate_graph_from_ast(graph, old_ast)
    await _initial_push(graph, sync_state, old_ast)
    counting_api.calls.clear()
    a_wdk_id = sync_state.wdk_step_ids["a"]

    a2 = _leaf("a", organism=["Pf3D7", "Pf7G8"])
    inner2 = _combine("inner", a2, b, op=CombineOp.UNION)
    outer2 = _combine("outer", inner2, c, op=CombineOp.INTERSECT)
    new_ast = _ast(outer2)

    graph2 = StrategyGraph("g1", "test", "plasmodb")
    _populate_graph_from_ast(graph2, new_ast)

    plan = plan_step_pushes(old_ast=old_ast, new_ast=new_ast, existing_wdk_ids=sync_state.wdk_step_ids)
    outcome = await push_steps_with_plan(graph2, sync_state, "plasmodb", plan)

    assert outcome.failed == []
    assert len(counting_api.calls) == 1
    call = counting_api.calls[0]
    assert call.name == "update_step_search_config"
    assert call.kwargs["step_id"] == a_wdk_id
    assert call.kwargs["search_name"] == "GenesByTaxon"


async def test_push_combine_operator_change_recreates_only_that_combine(
    counting_api: CountingStrategyAPI,
) -> None:
    a = _leaf("a", organism=["Pf3D7"])
    b = _leaf("b", organism=["PvP01"])
    c = _leaf("c", organism=["Pk"])
    inner = _combine("inner", a, b, op=CombineOp.UNION)
    outer = _combine("outer", inner, c, op=CombineOp.INTERSECT)
    old_ast = _ast(outer)

    graph = StrategyGraph("g1", "test", "plasmodb")
    sync_state = WDKSyncState()
    _populate_graph_from_ast(graph, old_ast)
    await _initial_push(graph, sync_state, old_ast)
    inner_wdk_id_before = sync_state.wdk_step_ids["inner"]
    counting_api.calls.clear()

    inner2 = _combine("inner", a, b, op=CombineOp.UNION)
    outer2 = _combine("outer", inner2, c, op=CombineOp.UNION)
    new_ast = _ast(outer2)
    graph2 = StrategyGraph("g1", "test", "plasmodb")
    _populate_graph_from_ast(graph2, new_ast)

    plan = plan_step_pushes(old_ast=old_ast, new_ast=new_ast, existing_wdk_ids=sync_state.wdk_step_ids)
    outcome = await push_steps_with_plan(graph2, sync_state, "plasmodb", plan)

    assert outcome.failed == []
    assert len(counting_api.calls) == 1
    call = counting_api.calls[0]
    assert call.name == "create_combined_step"
    assert call.kwargs["boolean_operator"] == "UNION"
    assert call.kwargs["primary_step_id"] == inner_wdk_id_before
    # outer combine got a new WDK id
    assert sync_state.wdk_step_ids["outer"] != sync_state.wdk_step_ids.get("inner") + 1


async def test_push_combine_operator_change_propagates_recreate_upward(
    counting_api: CountingStrategyAPI,
) -> None:
    a = _leaf("a", organism=["Pf3D7"])
    b = _leaf("b", organism=["PvP01"])
    c = _leaf("c", organism=["Pk"])
    inner = _combine("inner", a, b, op=CombineOp.UNION)
    outer = _combine("outer", inner, c, op=CombineOp.INTERSECT)
    old_ast = _ast(outer)

    graph = StrategyGraph("g1", "test", "plasmodb")
    sync_state = WDKSyncState()
    _populate_graph_from_ast(graph, old_ast)
    await _initial_push(graph, sync_state, old_ast)
    counting_api.calls.clear()

    # Change inner operator
    inner2 = _combine("inner", a, b, op=CombineOp.INTERSECT)
    outer2 = _combine("outer", inner2, c, op=CombineOp.INTERSECT)
    new_ast = _ast(outer2)
    graph2 = StrategyGraph("g1", "test", "plasmodb")
    _populate_graph_from_ast(graph2, new_ast)

    plan = plan_step_pushes(old_ast=old_ast, new_ast=new_ast, existing_wdk_ids=sync_state.wdk_step_ids)
    outcome = await push_steps_with_plan(graph2, sync_state, "plasmodb", plan)

    assert outcome.failed == []
    assert len(counting_api.calls) == 2
    assert counting_api.calls[0].name == "create_combined_step"
    assert counting_api.calls[0].kwargs["boolean_operator"] == "INTERSECT"
    new_inner_id = sync_state.wdk_step_ids["inner"]
    assert counting_api.calls[1].name == "create_combined_step"
    assert counting_api.calls[1].kwargs["primary_step_id"] == new_inner_id
    assert counting_api.calls[1].kwargs["boolean_operator"] == "INTERSECT"


async def test_push_with_added_step_creates_only_new_step(
    counting_api: CountingStrategyAPI,
) -> None:
    a = _leaf("a", organism=["Pf3D7"])
    b = _leaf("b", organism=["PvP01"])
    old_ast = _ast(_combine("c", a, b, op=CombineOp.UNION))

    graph = StrategyGraph("g1", "test", "plasmodb")
    sync_state = WDKSyncState()
    _populate_graph_from_ast(graph, old_ast)
    await _initial_push(graph, sync_state, old_ast)
    counting_api.calls.clear()

    d = _leaf("d", organism=["Pk"])
    inner = _combine("c", a, b, op=CombineOp.UNION)
    outer = _combine("outer", inner, d, op=CombineOp.INTERSECT)
    new_ast = _ast(outer)
    graph2 = StrategyGraph("g1", "test", "plasmodb")
    _populate_graph_from_ast(graph2, new_ast)

    plan = plan_step_pushes(old_ast=old_ast, new_ast=new_ast, existing_wdk_ids=sync_state.wdk_step_ids)
    outcome = await push_steps_with_plan(graph2, sync_state, "plasmodb", plan)

    assert outcome.failed == []
    # 1 leaf create (d) + 1 combined create (outer)
    names = [c.name for c in counting_api.calls]
    assert names == ["create_step", "create_combined_step"]
    assert counting_api.calls[0].kwargs["search_name"] == "GenesByTaxon"
    assert counting_api.calls[1].kwargs["boolean_operator"] == "INTERSECT"


async def test_push_combine_metadata_change_only_patches_via_update_properties(
    counting_api: CountingStrategyAPI,
) -> None:
    a = _leaf("a")
    b = _leaf("b")
    old_combine = StrategyStepNode(
        search_name="__combine__",
        primary_input=a,
        secondary_input=b,
        operator=CombineOp.UNION,
        display_name="A or B",
        id="c",
    )
    old_ast = _ast(old_combine)
    graph = StrategyGraph("g1", "test", "plasmodb")
    sync_state = WDKSyncState()
    _populate_graph_from_ast(graph, old_ast)
    await _initial_push(graph, sync_state, old_ast)
    combine_wdk_id = sync_state.wdk_step_ids["c"]
    counting_api.calls.clear()

    new_combine = StrategyStepNode(
        search_name="__combine__",
        primary_input=a,
        secondary_input=b,
        operator=CombineOp.UNION,
        display_name="A union B",
        id="c",
    )
    new_ast = _ast(new_combine)
    graph2 = StrategyGraph("g1", "test", "plasmodb")
    _populate_graph_from_ast(graph2, new_ast)

    plan = plan_step_pushes(old_ast=old_ast, new_ast=new_ast, existing_wdk_ids=sync_state.wdk_step_ids)
    outcome = await push_steps_with_plan(graph2, sync_state, "plasmodb", plan)

    assert outcome.failed == []
    assert len(counting_api.calls) == 1
    call = counting_api.calls[0]
    assert call.name == "update_step_properties"
    assert call.kwargs["step_id"] == combine_wdk_id
    assert call.kwargs["custom_name"] == "A union B"

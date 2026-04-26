from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.domain.strategy.ops import ColocationParams, CombineOp
from pathfinder.domain.strategy.strategy_ast import StrategyAst
from pathfinder.integrations.veupathdb.wdk_models import (
    NewStepSpec,
    PatchStepSpec,
    WDKIdentifier,
    WDKSearchConfig,
    WDKStep,
)
from pathfinder.persistence.models import Conversation
from pathfinder.persistence.repositories import ConversationUpdate
from pathfinder.platform.errors import ErrorCode, NotFoundError
from pathfinder.services.strategies import (
    plan_normalize,
    step_patch,
    step_wdk_push,
)
from pathfinder.services.strategies import (
    sync as sync_module,
)
from pathfinder.services.strategies.step_patch import apply_step_patch
from pathfinder.services.strategies.sync import SyncResult
from pathfinder.transport.http.schemas import StepPatchRequest


@dataclass
class _CallRecord:
    name: str
    kwargs: dict[str, Any]


@dataclass
class CountingStrategyAPI:
    next_id: int = 1000
    calls: list[_CallRecord] = field(default_factory=list)

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


class FakeConvRepo:
    def __init__(self, conversation: Conversation) -> None:
        self.conversation = conversation
        self.update_calls: list[ConversationUpdate] = []
        self.commit_partial_calls: int = 0

    async def get_by_id_with_strategy_lock(
        self, conversation_id: UUID
    ) -> Conversation | None:
        if conversation_id == self.conversation.id:
            return self.conversation
        return None

    async def update_conversation(
        self, conversation_id: UUID, upd: ConversationUpdate
    ) -> None:
        del conversation_id
        self.update_calls.append(upd)
        if upd.strategy_ast is not None:
            self.conversation.strategy_ast = upd.strategy_ast.model_dump(
                by_alias=True, exclude_none=True, mode="json"
            )
        if upd.wdk_strategy_id_set:
            self.conversation.wdk_strategy_id = upd.wdk_strategy_id

    async def commit_partial(self) -> None:
        self.commit_partial_calls += 1


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
    display_name: str | None = None,
    coloc: ColocationParams | None = None,
) -> StrategyStepNode:
    return StrategyStepNode(
        search_name="__combine__",
        primary_input=primary,
        secondary_input=secondary,
        operator=op,
        display_name=display_name,
        colocation_params=coloc,
        id=step_id,
    )


def _ast(root: StrategyStepNode, *, wdk_step_ids: dict[str, int] | None = None) -> StrategyAst:
    return StrategyAst(
        record_type="transcript",
        root=root,
        wdk_step_ids=wdk_step_ids,
    )


def _make_repo(ast: StrategyAst, *, wdk_strategy_id: int | None = 555) -> FakeConvRepo:
    conv = Conversation(
        id=uuid4(),
        user_id=uuid4(),
        name="Test strategy",
        site_id="plasmodb",
        wdk_strategy_id=wdk_strategy_id,
        strategy_ast=ast.model_dump(by_alias=True, exclude_none=True, mode="json"),
    )
    return FakeConvRepo(conv)


@pytest.fixture
def patched_canonicalize(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _identity(*, strategy_ast: StrategyAst, site_id: str, **_kwargs: Any) -> StrategyAst:
        del site_id
        return strategy_ast

    monkeypatch.setattr(plan_normalize, "canonicalize_strategy_ast_parameters", _identity)
    monkeypatch.setattr(
        step_patch, "canonicalize_strategy_ast_parameters", _identity
    )


@pytest.fixture
def counting_api(monkeypatch: pytest.MonkeyPatch) -> CountingStrategyAPI:
    api = CountingStrategyAPI()
    monkeypatch.setattr(step_wdk_push, "get_strategy_api", lambda _site_id: api)
    monkeypatch.setattr(sync_module, "get_strategy_api", lambda _site_id: api)

    async def _noop_reconcile(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(step_patch, "reconcile_sync_state_with_wdk", _noop_reconcile)

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


def _make_full_strategy_with_existing_wdk_ids() -> tuple[StrategyAst, dict[str, int]]:
    a = _leaf("step_a", organism=["Pf3D7"])
    b = _leaf("step_b", organism=["PvP01"])
    c = _leaf("step_c", organism=["Pk"])
    inner = _combine("step_inner", a, b, op=CombineOp.UNION)
    outer = _combine("step_outer", inner, c, op=CombineOp.INTERSECT)
    wdk_ids = {
        "step_a": 100,
        "step_b": 101,
        "step_c": 102,
        "step_inner": 103,
        "step_outer": 104,
    }
    return _ast(outer, wdk_step_ids=wdk_ids), wdk_ids


@pytest.mark.usefixtures("patched_canonicalize")
async def test_patch_leaf_param_change_emits_one_wdk_call(
    counting_api: CountingStrategyAPI,
) -> None:
    ast, wdk_ids = _make_full_strategy_with_existing_wdk_ids()
    repo = _make_repo(ast)

    new_params = {"organism": ["Pf3D7", "Pf7G8"]}
    response = await apply_step_patch(
        conv_repo=repo,
        strategy_id=repo.conversation.id,
        step_id="step_a",
        site_id="plasmodb",
        patch=StepPatchRequest(parameters=new_params),
    )

    assert len(counting_api.calls) == 1
    call = counting_api.calls[0]
    assert call.name == "update_step_search_config"
    assert call.kwargs["step_id"] == wdk_ids["step_a"]
    assert call.kwargs["search_name"] == "GenesByTaxon"
    assert call.kwargs["parameters"] == {"organism": '["Pf3D7", "Pf7G8"]'}
    assert response.parameters == new_params
    assert response.id == "step_a"
    assert response.search_name == "GenesByTaxon"


@pytest.mark.usefixtures("patched_canonicalize")
async def test_patch_combine_operator_change_emits_create_combined_step_and_update_strategy(
    counting_api: CountingStrategyAPI,
) -> None:
    ast, wdk_ids = _make_full_strategy_with_existing_wdk_ids()
    repo = _make_repo(ast)
    inner_wdk_id = wdk_ids["step_inner"]

    response = await apply_step_patch(
        conv_repo=repo,
        strategy_id=repo.conversation.id,
        step_id="step_inner",
        site_id="plasmodb",
        patch=StepPatchRequest(operator=CombineOp.INTERSECT),
    )

    create_calls = [c for c in counting_api.calls if c.name == "create_combined_step"]
    assert len(create_calls) == 2
    assert create_calls[0].kwargs["boolean_operator"] == "INTERSECT"
    assert create_calls[0].kwargs["primary_step_id"] == wdk_ids["step_a"]
    assert create_calls[0].kwargs["secondary_step_id"] == wdk_ids["step_b"]
    new_inner_id = create_calls[0].kwargs.get("custom_name")
    del new_inner_id
    assert create_calls[1].kwargs["boolean_operator"] == "INTERSECT"
    assert response.operator == "INTERSECT"
    assert response.id == "step_inner"
    assert repo.conversation.strategy_ast["wdkStepIds"]["step_inner"] != inner_wdk_id


@pytest.mark.usefixtures("patched_canonicalize")
async def test_patch_leaf_display_name_only_emits_update_step_search_config(
    counting_api: CountingStrategyAPI,
) -> None:
    # Leaf PATCH always re-pushes parameters via update_step_search_config —
    # WDK has no leaf-only display-name PATCH; the planner still emits PATCH
    # for the display-name change.
    ast, wdk_ids = _make_full_strategy_with_existing_wdk_ids()
    repo = _make_repo(ast)

    response = await apply_step_patch(
        conv_repo=repo,
        strategy_id=repo.conversation.id,
        step_id="step_a",
        site_id="plasmodb",
        patch=StepPatchRequest(display_name="Falciparum strains"),
    )

    assert len(counting_api.calls) == 1
    call = counting_api.calls[0]
    assert call.name == "update_step_search_config"
    assert call.kwargs["step_id"] == wdk_ids["step_a"]
    assert call.kwargs["search_name"] == "GenesByTaxon"
    assert call.kwargs["parameters"] == {"organism": '["Pf3D7"]'}
    assert response.display_name == "Falciparum strains"


@pytest.mark.usefixtures("patched_canonicalize")
async def test_patch_combine_display_name_only_emits_update_step_properties(
    counting_api: CountingStrategyAPI,
) -> None:
    ast, wdk_ids = _make_full_strategy_with_existing_wdk_ids()
    repo = _make_repo(ast)

    response = await apply_step_patch(
        conv_repo=repo,
        strategy_id=repo.conversation.id,
        step_id="step_inner",
        site_id="plasmodb",
        patch=StepPatchRequest(display_name="A union B"),
    )

    assert len(counting_api.calls) == 1
    call = counting_api.calls[0]
    assert call.name == "update_step_properties"
    assert call.kwargs["step_id"] == wdk_ids["step_inner"]
    assert call.kwargs["custom_name"] == "A union B"
    assert response.display_name == "A union B"
    assert response.operator == "UNION"


@pytest.mark.usefixtures("patched_canonicalize", "counting_api")
async def test_patch_unknown_step_id_returns_404() -> None:
    ast, _ = _make_full_strategy_with_existing_wdk_ids()
    repo = _make_repo(ast)

    with pytest.raises(NotFoundError) as exc_info:
        await apply_step_patch(
            conv_repo=repo,
            strategy_id=repo.conversation.id,
            step_id="step_does_not_exist",
            site_id="plasmodb",
            patch=StepPatchRequest(display_name="anything"),
        )

    assert exc_info.value.code == ErrorCode.STEP_NOT_FOUND
    assert exc_info.value.status == 404


@pytest.mark.usefixtures("patched_canonicalize")
async def test_patch_with_no_changes_makes_zero_wdk_calls(
    counting_api: CountingStrategyAPI,
) -> None:
    ast, _ = _make_full_strategy_with_existing_wdk_ids()
    repo = _make_repo(ast)

    response = await apply_step_patch(
        conv_repo=repo,
        strategy_id=repo.conversation.id,
        step_id="step_a",
        site_id="plasmodb",
        patch=StepPatchRequest(parameters={"organism": ["Pf3D7"]}),
    )

    assert counting_api.calls == []
    assert response.parameters == {"organism": ["Pf3D7"]}


@pytest.mark.usefixtures("patched_canonicalize")
async def test_patch_clearing_colocation_params_when_switching_off_colocate(
    counting_api: CountingStrategyAPI,
) -> None:
    a = _leaf("step_a", organism=["Pf3D7"])
    b = _leaf("step_b", organism=["PvP01"])
    coloc = ColocationParams()
    inner = _combine("step_inner", a, b, op=CombineOp.COLOCATE, coloc=coloc)
    wdk_ids = {"step_a": 200, "step_b": 201, "step_inner": 202}
    ast = _ast(inner, wdk_step_ids=wdk_ids)
    repo = _make_repo(ast)

    response = await apply_step_patch(
        conv_repo=repo,
        strategy_id=repo.conversation.id,
        step_id="step_inner",
        site_id="plasmodb",
        patch=StepPatchRequest(operator=CombineOp.UNION, colocation_params=None),
    )

    create_calls = [c for c in counting_api.calls if c.name == "create_combined_step"]
    assert len(create_calls) == 1
    assert create_calls[0].kwargs["boolean_operator"] == "UNION"
    assert response.operator == "UNION"
    assert response.colocation_params is None


def test_patch_invalid_combine_operator_value_rejected() -> None:
    with pytest.raises(ValidationError):
        StepPatchRequest.model_validate({"operator": "GARBAGE"})


@pytest.mark.usefixtures("patched_canonicalize", "counting_api")
async def test_patch_only_sets_what_was_explicitly_passed() -> None:
    a = StrategyStepNode(
        search_name="GenesByTaxon",
        parameters={"organism": ["Pf3D7"]},
        display_name="Original Name",
        id="step_a",
    )
    b = _leaf("step_b", organism=["PvP01"])
    inner = _combine("step_inner", a, b, op=CombineOp.UNION)
    wdk_ids = {"step_a": 300, "step_b": 301, "step_inner": 302}
    ast = _ast(inner, wdk_step_ids=wdk_ids)
    repo = _make_repo(ast)

    patch = StepPatchRequest(parameters={"organism": ["Pf3D7", "Pv"]})
    assert patch.model_fields_set == {"parameters"}

    response = await apply_step_patch(
        conv_repo=repo,
        strategy_id=repo.conversation.id,
        step_id="step_a",
        site_id="plasmodb",
        patch=patch,
    )

    assert response.display_name == "Original Name"
    assert response.parameters == {"organism": ["Pf3D7", "Pv"]}

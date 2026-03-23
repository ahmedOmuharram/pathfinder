"""Integration tests for strategy compilation pipeline (domain/strategy/compile.py).

Verifies that compile_strategy correctly orchestrates WDK step creation,
tree construction, operator handling, AnswerParam coercion, and dataset upload.
Uses a mock StrategyCompilerAPI to capture outbound WDK payloads.

WDK contracts validated:
- Search steps → POST /users/{id}/steps with searchName + searchConfig
- Combine steps → boolean_question search with bq_left_op/bq_right_op/bq_operator
- Transform steps → AnswerParams forced to "" (wiring via stepTree)
- Dataset upload → raw gene IDs auto-uploaded, param replaced with int ID
- Step tree → recursive WDKStepTree with primaryInput/secondaryInput
"""

from dataclasses import dataclass, field
from unittest.mock import AsyncMock

import pytest

from veupath_chatbot.domain.strategy.ast import PlanStepNode, StrategyAST
from veupath_chatbot.domain.strategy.compile import (
    CompilationResult,
    compile_strategy,
)
from veupath_chatbot.domain.strategy.ops import ColocationParams, CombineOp
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    NewStepSpec,
    PatchStepSpec,
    WDKDatasetConfig,
    WDKIdentifier,
    WDKSearch,
    WDKSearchResponse,
    WDKValidation,
)
from veupath_chatbot.platform.errors import ValidationError
from veupath_chatbot.platform.types import JSONObject


@dataclass
class StepCall:
    """Captured call to create_step / create_combined_step / create_transform_step."""

    method: str
    kwargs: dict[str, object] = field(default_factory=dict)


class FakeCompilerAPI:
    """Mock StrategyCompilerAPI that captures all WDK calls and returns sequential IDs.

    Implements the StrategyCompilerAPI protocol for testing compilation
    without hitting WDK. Each step creation returns {id: N} with incrementing N.
    """

    def __init__(self) -> None:
        self.calls: list[StepCall] = []
        self._next_id = 100
        # Mock client for param spec loading
        self.client = AsyncMock()
        # Default: get_search_details returns a search with no params
        self.client.get_search_details = AsyncMock(side_effect=self._fake_search_details)
        self.client.get_search_details_with_params = AsyncMock(
            side_effect=self._fake_search_details_with_params
        )

    def _make_search_response(self) -> WDKSearchResponse:
        """Return a minimal WDKSearchResponse with no params."""
        search = WDKSearch(
            url_segment="test",
            full_name="TestSearch",
            display_name="Test",
            parameters=None,
            groups=[],
        )
        return WDKSearchResponse(
            search_data=search,
            validation=WDKValidation(),
        )

    async def _fake_search_details(
        self, record_type: str, search_name: str, *, expand_params: bool = False
    ) -> WDKSearchResponse:
        """Return minimal WDKSearchResponse with no params."""
        return self._make_search_response()

    async def _fake_search_details_with_params(
        self,
        record_type: str,
        search_name: str,
        context: JSONObject,
        *,
        expand_params: bool = False,
    ) -> WDKSearchResponse:
        return self._make_search_response()

    def _alloc_id(self) -> int:
        step_id = self._next_id
        self._next_id += 1
        return step_id

    async def create_step(
        self,
        spec: NewStepSpec,
        record_type: str,
        user_id: str | None = None,
    ) -> WDKIdentifier:
        step_id = self._alloc_id()
        self.calls.append(
            StepCall(
                method="create_step",
                kwargs={
                    "record_type": record_type,
                    "search_name": spec.search_name,
                    "parameters": dict(spec.search_config.parameters),
                    "custom_name": spec.custom_name,
                    "wdk_weight": spec.search_config.wdk_weight,
                    "returned_id": step_id,
                },
            )
        )
        return WDKIdentifier(id=step_id)

    async def create_combined_step(  # noqa: PLR0913
        self,
        primary_step_id: int,
        secondary_step_id: int,
        boolean_operator: str,
        record_type: str,
        *,
        spec_overrides: PatchStepSpec | None = None,
        wdk_weight: int | None = None,
        user_id: str | None = None,
    ) -> WDKIdentifier:
        step_id = self._alloc_id()
        self.calls.append(
            StepCall(
                method="create_combined_step",
                kwargs={
                    "primary_step_id": primary_step_id,
                    "secondary_step_id": secondary_step_id,
                    "boolean_operator": boolean_operator,
                    "record_type": record_type,
                    "custom_name": spec_overrides.custom_name if spec_overrides else None,
                    "wdk_weight": wdk_weight,
                    "returned_id": step_id,
                },
            )
        )
        return WDKIdentifier(id=step_id)

    async def create_transform_step(
        self,
        spec: NewStepSpec,
        input_step_id: int,
        record_type: str = "transcript",
        *,
        user_id: str | None = None,
    ) -> WDKIdentifier:
        step_id = self._alloc_id()
        self.calls.append(
            StepCall(
                method="create_transform_step",
                kwargs={
                    "input_step_id": input_step_id,
                    "transform_name": spec.search_name,
                    "parameters": dict(spec.search_config.parameters),
                    "record_type": record_type,
                    "custom_name": spec.custom_name,
                    "wdk_weight": spec.search_config.wdk_weight,
                    "returned_id": step_id,
                },
            )
        )
        return WDKIdentifier(id=step_id)

    async def create_dataset(self, config: WDKDatasetConfig, user_id: str | None = None) -> int:
        ds_id = self._alloc_id()
        self.calls.append(
            StepCall(method="create_dataset", kwargs={"config": config, "returned_id": ds_id})
        )
        return ds_id


# ── Single search step compilation ────────────────────────────────


class TestCompileSearchStep:
    """Verifies: single leaf step → one create_step call with correct payload."""

    @pytest.mark.asyncio
    async def test_single_search_creates_one_step(self) -> None:
        """Single search step → one create_step call.

        Uses empty parameters because the fake API returns empty param specs;
        ParameterNormalizer rejects any param not in specs.
        """
        api = FakeCompilerAPI()
        ast = StrategyAST(
            record_type="transcript",
            root=PlanStepNode(
                search_name="GenesByTaxon",
                parameters={},
                id="s1",
            ),
        )
        result = await compile_strategy(ast, api, resolve_record_type=False)

        assert isinstance(result, CompilationResult)
        assert len(result.steps) == 1
        assert result.steps[0].local_id == "s1"
        assert result.steps[0].step_type == "search"
        assert result.root_step_id == 100  # First allocated ID

        # Verify WDK call
        assert len(api.calls) == 1
        call = api.calls[0]
        assert call.method == "create_step"
        assert call.kwargs["search_name"] == "GenesByTaxon"
        assert call.kwargs["record_type"] == "transcript"

    @pytest.mark.asyncio
    async def test_step_tree_is_single_node(self) -> None:
        api = FakeCompilerAPI()
        ast = StrategyAST(
            record_type="transcript",
            root=PlanStepNode(search_name="GenesByTaxon", parameters={}, id="s1"),
        )
        result = await compile_strategy(ast, api, resolve_record_type=False)

        assert result.step_tree.step_id == 100
        assert result.step_tree.primary_input is None
        assert result.step_tree.secondary_input is None


# ── Combine step compilation ──────────────────────────────────────


class TestCompileCombineStep:
    """Verifies: combine → left + right created first, then combined step.

    WDK contract: boolean combine uses `create_combined_step` with
    INTERSECT/UNION/MINUS operator string matching CombineOp.
    Steps are created bottom-up (leaves before root).
    """

    @pytest.mark.asyncio
    async def test_combine_creates_three_steps(self) -> None:
        api = FakeCompilerAPI()
        left = PlanStepNode(
            search_name="GenesByTaxon",
            parameters={},
            id="left",
        )
        right = PlanStepNode(
            search_name="GenesByTextSearch",
            parameters={},
            id="right",
        )
        ast = StrategyAST(
            record_type="transcript",
            root=PlanStepNode(
                search_name="combine",
                primary_input=left,
                secondary_input=right,
                operator=CombineOp.INTERSECT,
                id="root",
            ),
        )
        result = await compile_strategy(ast, api, resolve_record_type=False)

        # 3 steps: left search, right search, combine
        assert len(result.steps) == 3
        assert len(api.calls) == 3

        # Leaves created first (bottom-up DFS)
        assert api.calls[0].method == "create_step"
        assert api.calls[0].kwargs["search_name"] == "GenesByTaxon"
        assert api.calls[1].method == "create_step"
        assert api.calls[1].kwargs["search_name"] == "GenesByTextSearch"

        # Combine last
        combine_call = api.calls[2]
        assert combine_call.method == "create_combined_step"
        assert combine_call.kwargs["boolean_operator"] == "INTERSECT"
        assert combine_call.kwargs["primary_step_id"] == 100  # left's WDK ID
        assert combine_call.kwargs["secondary_step_id"] == 101  # right's WDK ID

    @pytest.mark.asyncio
    async def test_combine_step_tree_structure(self) -> None:
        """Step tree must wire primaryInput and secondaryInput."""
        api = FakeCompilerAPI()
        left = PlanStepNode(search_name="S1", parameters={}, id="l")
        right = PlanStepNode(search_name="S2", parameters={}, id="r")
        ast = StrategyAST(
            record_type="transcript",
            root=PlanStepNode(
                search_name="bq",
                primary_input=left,
                secondary_input=right,
                operator=CombineOp.UNION,
                id="root",
            ),
        )
        result = await compile_strategy(ast, api, resolve_record_type=False)

        tree = result.step_tree
        assert tree.step_id == 102  # combine step
        assert tree.primary_input is not None
        assert tree.primary_input.step_id == 100  # left
        assert tree.secondary_input is not None
        assert tree.secondary_input.step_id == 101  # right


# ── Transform step compilation ────────────────────────────────────


class TestCompileTransformStep:
    """Verifies: transform → input compiled first, then transform step.

    WDK contract: AnswerParam (input-step) must be "" at creation;
    wiring happens via stepTree.
    """

    @pytest.mark.asyncio
    async def test_transform_creates_two_steps(self) -> None:
        api = FakeCompilerAPI()
        child = PlanStepNode(
            search_name="GenesByTaxon", parameters={}, id="child"
        )
        ast = StrategyAST(
            record_type="transcript",
            root=PlanStepNode(
                search_name="GenesByOrthologPattern",
                primary_input=child,
                parameters={},
                id="transform",
            ),
        )
        result = await compile_strategy(ast, api, resolve_record_type=False)

        assert len(result.steps) == 2
        # Input first, transform second
        assert api.calls[0].method == "create_step"
        assert api.calls[0].kwargs["search_name"] == "GenesByTaxon"
        assert api.calls[1].method == "create_transform_step"
        assert api.calls[1].kwargs["transform_name"] == "GenesByOrthologPattern"
        assert api.calls[1].kwargs["input_step_id"] == 100

    @pytest.mark.asyncio
    async def test_transform_step_tree_has_primary_input(self) -> None:
        api = FakeCompilerAPI()
        child = PlanStepNode(search_name="S1", parameters={}, id="child")
        ast = StrategyAST(
            record_type="transcript",
            root=PlanStepNode(
                search_name="Transform",
                primary_input=child,
                parameters={},
                id="xform",
            ),
        )
        result = await compile_strategy(ast, api, resolve_record_type=False)

        tree = result.step_tree
        assert tree.step_id == 101  # transform
        assert tree.primary_input is not None
        assert tree.primary_input.step_id == 100  # child
        assert tree.secondary_input is None


# ── Record type resolution ────────────────────────────────────────


class TestRecordTypeResolution:
    @pytest.mark.asyncio
    async def test_mixed_record_types_raises(self) -> None:
        """Searches from different record types cannot be combined."""
        api = FakeCompilerAPI()

        async def resolve_rt(search_name: str) -> str | None:
            return "transcript" if search_name == "S1" else "gene"

        left = PlanStepNode(search_name="S1", parameters={}, id="l")
        right = PlanStepNode(search_name="S2", parameters={}, id="r")
        ast = StrategyAST(
            record_type="transcript",
            root=PlanStepNode(
                search_name="bq",
                primary_input=left,
                secondary_input=right,
                operator=CombineOp.INTERSECT,
                id="root",
            ),
        )
        with pytest.raises(ValidationError, match="multiple record types"):
            await compile_strategy(
                ast, api, resolve_record_type=True, resolve_search_record_type=resolve_rt
            )

    @pytest.mark.asyncio
    async def test_consistent_record_type_accepted(self) -> None:
        api = FakeCompilerAPI()

        async def resolve_rt(search_name: str) -> str | None:
            return "transcript"

        ast = StrategyAST(
            record_type="transcript",
            root=PlanStepNode(search_name="S1", parameters={}, id="s1"),
        )
        result = await compile_strategy(
            ast, api, resolve_record_type=True, resolve_search_record_type=resolve_rt
        )
        assert result.root_step_id == 100


# ── Colocation compilation ────────────────────────────────────────


class TestCompileColocation:
    """Verifies: COLOCATE → GenesBySpanLogic transform with correct params.

    WDK contract: GenesBySpanLogic requires span_sentence="sentence",
    AnswerParams span_a/span_b="" (wired via stepTree).
    """

    @pytest.mark.asyncio
    async def test_colocation_uses_genes_by_span_logic(self) -> None:
        api = FakeCompilerAPI()
        left = PlanStepNode(search_name="S1", parameters={}, id="l")
        right = PlanStepNode(search_name="S2", parameters={}, id="r")
        ast = StrategyAST(
            record_type="transcript",
            root=PlanStepNode(
                search_name="coloc",
                primary_input=left,
                secondary_input=right,
                operator=CombineOp.COLOCATE,
                colocation_params=ColocationParams(
                    upstream=1000, downstream=500, strand="same"
                ),
                id="root",
            ),
        )
        await compile_strategy(ast, api, resolve_record_type=False)

        # Last call should be create_transform_step for GenesBySpanLogic
        coloc_call = api.calls[-1]
        assert coloc_call.method == "create_transform_step"
        assert coloc_call.kwargs["transform_name"] == "GenesBySpanLogic"
        params = coloc_call.kwargs["parameters"]
        assert isinstance(params, dict)
        assert params["span_sentence"] == "sentence"
        assert params["span_begin_offset_a"] == "1000"
        assert params["span_end_offset_a"] == "500"

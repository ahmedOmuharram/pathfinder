"""Tests for strategy compiler (domain/strategy/compile.py)."""

from unittest.mock import AsyncMock

import pytest

from veupath_chatbot.domain.strategy.ast import (
    PlanStepNode,
    StepAnalysis,
    StepFilter,
    StepReport,
    StepTreeNode,
    StrategyAST,
)
from veupath_chatbot.domain.strategy.compile import (
    CompilationResult,
    CompiledStep,
    StrategyCompiler,
    _extract_wdk_step_id,
    apply_step_decorations,
    compile_strategy,
)
from veupath_chatbot.domain.strategy.ops import ColocationParams, CombineOp
from veupath_chatbot.platform.errors import InternalError, ValidationError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _default_search_details() -> dict:
    """Return search details with specs matching the default test parameters."""
    return {
        "searchData": {
            "parameters": [
                {"name": "text_expression", "type": "string"},
                {"name": "taxon", "type": "string"},
                {"name": "organism", "type": "string"},
            ],
        },
    }


def _mock_api() -> AsyncMock:
    """Build a mock StrategyAPI with all methods stubbed."""
    api = AsyncMock()
    # Default: client.get_search_details returns specs that match test params
    api.client.get_search_details = AsyncMock(return_value=_default_search_details())
    api.client.get_search_details_with_params = AsyncMock(
        return_value=_default_search_details()
    )
    api.client.get_record_types = AsyncMock(return_value=[])
    api.client.get_searches = AsyncMock(return_value=[])
    # Default: create_step returns dict with id
    api.create_step = AsyncMock(return_value={"id": 100})
    api.create_combined_step = AsyncMock(return_value={"id": 200})
    api.create_transform_step = AsyncMock(return_value={"id": 300})
    api.create_dataset = AsyncMock(return_value=999)
    # Decoration methods
    api.set_step_filter = AsyncMock(return_value={})
    api.run_step_analysis = AsyncMock(return_value={})
    api.run_step_report = AsyncMock(return_value={})
    return api


def _search_node(
    search_name: str = "GenesByTextSearch",
    step_id: str = "s1",
    params: dict | None = None,
) -> PlanStepNode:
    return PlanStepNode(
        search_name=search_name,
        parameters=params or {"text_expression": "kinase"},
        id=step_id,
    )


def _combine_node(
    left: PlanStepNode,
    right: PlanStepNode,
    op: CombineOp = CombineOp.INTERSECT,
    step_id: str = "c1",
) -> PlanStepNode:
    return PlanStepNode(
        search_name="boolean_question_gene",
        primary_input=left,
        secondary_input=right,
        operator=op,
        id=step_id,
    )


def _transform_node(
    child: PlanStepNode,
    search_name: str = "GenesByOrthology",
    step_id: str = "t1",
) -> PlanStepNode:
    return PlanStepNode(
        search_name=search_name,
        primary_input=child,
        parameters={"taxon": "Plasmodium"},
        id=step_id,
    )


# ---------------------------------------------------------------------------
# _extract_wdk_step_id
# ---------------------------------------------------------------------------


class TestExtractWdkStepId:
    def test_extracts_int(self) -> None:
        assert _extract_wdk_step_id({"id": 42}) == 42

    def test_extracts_float_coerced(self) -> None:
        assert _extract_wdk_step_id({"id": 42.0}) == 42

    def test_missing_id_raises(self) -> None:
        with pytest.raises(TypeError, match="numeric step ID"):
            _extract_wdk_step_id({})

    def test_string_id_raises(self) -> None:
        with pytest.raises(TypeError, match="numeric step ID"):
            _extract_wdk_step_id({"id": "not_a_number"})

    def test_none_id_raises(self) -> None:
        with pytest.raises(TypeError, match="numeric step ID"):
            _extract_wdk_step_id({"id": None})


# ---------------------------------------------------------------------------
# CompiledStep / CompilationResult
# ---------------------------------------------------------------------------


class TestCompiledStepToDict:
    def test_compilation_result_to_dict(self) -> None:
        steps = [
            CompiledStep(
                local_id="s1",
                wdk_step_id=100,
                step_type="search",
                display_name="Search 1",
            ),
            CompiledStep(
                local_id="s2",
                wdk_step_id=101,
                step_type="search",
                display_name="Search 2",
            ),
        ]
        tree = StepTreeNode(
            step_id=200,
            primary_input=StepTreeNode(step_id=100),
            secondary_input=StepTreeNode(step_id=101),
        )
        result = CompilationResult(steps=steps, step_tree=tree, root_step_id=200)
        d = result.to_dict()
        assert d["rootStepId"] == 200
        steps_list = d["steps"]
        assert isinstance(steps_list, list)
        assert len(steps_list) == 2
        step_0 = steps_list[0]
        assert isinstance(step_0, dict)
        assert step_0["localId"] == "s1"
        assert step_0["wdkStepId"] == 100
        assert step_0["type"] == "search"
        assert step_0["displayName"] == "Search 1"
        step_tree = d["stepTree"]
        assert isinstance(step_tree, dict)
        assert step_tree["stepId"] == 200


# ---------------------------------------------------------------------------
# StrategyCompiler — search step
# ---------------------------------------------------------------------------


class TestCompileSearchStep:
    async def test_compiles_single_search(self) -> None:
        api = _mock_api()
        api.create_step.return_value = {"id": 100}

        step = _search_node()
        strategy = StrategyAST(record_type="gene", root=step)
        compiler = StrategyCompiler(api, resolve_record_type=False)
        result = await compiler.compile(strategy)

        assert result.root_step_id == 100
        assert len(result.steps) == 1
        assert result.steps[0].local_id == "s1"
        assert result.steps[0].wdk_step_id == 100
        assert result.steps[0].step_type == "search"
        api.create_step.assert_awaited_once()

    async def test_search_with_display_name(self) -> None:
        api = _mock_api()
        api.create_step.return_value = {"id": 100}
        step = _search_node()
        step.display_name = "My Search"
        strategy = StrategyAST(record_type="gene", root=step)
        compiler = StrategyCompiler(api, resolve_record_type=False)
        result = await compiler.compile(strategy)
        assert result.steps[0].display_name == "My Search"


# ---------------------------------------------------------------------------
# StrategyCompiler — combine step
# ---------------------------------------------------------------------------


class TestCompileCombineStep:
    async def test_compiles_combine(self) -> None:
        api = _mock_api()
        step_ids = iter([{"id": 100}, {"id": 101}, {"id": 200}])
        api.create_step.side_effect = lambda **kw: next(step_ids)
        api.create_combined_step.return_value = {"id": 200}

        left = _search_node(step_id="s1")
        right = _search_node(step_id="s2", search_name="GenesByGoTerm")
        root = _combine_node(left, right)
        strategy = StrategyAST(record_type="gene", root=root)

        compiler = StrategyCompiler(api, resolve_record_type=False)
        result = await compiler.compile(strategy)

        assert result.root_step_id == 200
        assert len(result.steps) == 3
        step_types = {s.step_type for s in result.steps}
        assert "search" in step_types
        assert "combine" in step_types
        api.create_combined_step.assert_awaited_once()

    async def test_combine_missing_inputs_raises(self) -> None:
        api = _mock_api()
        node = PlanStepNode(
            search_name="bool",
            primary_input=None,
            secondary_input=None,
            operator=CombineOp.INTERSECT,
            id="c1",
        )
        # Force kind to "combine" by setting both inputs, then clear them
        # Actually, infer_kind() returns "search" here. We need to test the
        # explicit guard in _compile_combine. Let's call it directly.
        compiler = StrategyCompiler(api, resolve_record_type=False)
        with pytest.raises(ValueError, match="missing inputs"):
            await compiler._compile_combine(node, "gene")

    async def test_combine_missing_operator_raises(self) -> None:
        api = _mock_api()
        left = _search_node(step_id="s1")
        right = _search_node(step_id="s2")
        node = PlanStepNode(
            search_name="bool",
            primary_input=left,
            secondary_input=right,
            operator=None,
            id="c1",
        )
        compiler = StrategyCompiler(api, resolve_record_type=False)
        with pytest.raises(ValueError, match="missing operator"):
            await compiler._compile_combine(node, "gene")


# ---------------------------------------------------------------------------
# StrategyCompiler — transform step
# ---------------------------------------------------------------------------


class TestCompileTransformStep:
    async def test_compiles_transform(self) -> None:
        api = _mock_api()
        api.create_step.return_value = {"id": 100}
        api.create_transform_step.return_value = {"id": 300}

        child = _search_node()
        root = _transform_node(child)
        strategy = StrategyAST(record_type="gene", root=root)

        compiler = StrategyCompiler(api, resolve_record_type=False)
        result = await compiler.compile(strategy)

        assert result.root_step_id == 300
        assert len(result.steps) == 2
        api.create_transform_step.assert_awaited_once()

    async def test_transform_missing_input_raises(self) -> None:
        api = _mock_api()
        node = PlanStepNode(
            search_name="GenesByOrthology",
            primary_input=None,
            id="t1",
        )
        compiler = StrategyCompiler(api, resolve_record_type=False)
        with pytest.raises(ValueError, match="missing primaryInput"):
            await compiler._compile_transform(node, "gene")


# ---------------------------------------------------------------------------
# StrategyCompiler — colocation
# ---------------------------------------------------------------------------


class TestCompileColocation:
    async def test_colocate_creates_transform_step(self) -> None:
        api = _mock_api()
        step_ids = iter([{"id": 100}, {"id": 101}])
        api.create_step.side_effect = lambda **kw: next(step_ids)
        api.create_transform_step.return_value = {"id": 300}

        left = _search_node(step_id="s1")
        right = _search_node(step_id="s2")
        root = PlanStepNode(
            search_name="bool",
            primary_input=left,
            secondary_input=right,
            operator=CombineOp.COLOCATE,
            colocation_params=ColocationParams(
                upstream=500, downstream=200, strand="same"
            ),
            id="c1",
        )
        strategy = StrategyAST(record_type="gene", root=root)

        compiler = StrategyCompiler(api, resolve_record_type=False)
        result = await compiler.compile(strategy)

        assert result.root_step_id == 300
        # Verify transform was called (colocation uses create_transform_step)
        api.create_transform_step.assert_awaited_once()
        call_kwargs = api.create_transform_step.call_args.kwargs
        assert call_kwargs["transform_name"] == "GenesBySpanLogic"
        params = call_kwargs["parameters"]
        assert params["span_begin_offset_a"] == "500"
        assert params["span_end_offset_a"] == "200"
        assert params["span_sentence"] == "sentence"

    async def test_colocate_without_params_still_works(self) -> None:
        """When colocation_params is None, no upstream/downstream/strand params added."""
        api = _mock_api()
        step_ids = iter([{"id": 100}, {"id": 101}])
        api.create_step.side_effect = lambda **kw: next(step_ids)
        api.create_transform_step.return_value = {"id": 300}

        left = _search_node(step_id="s1")
        right = _search_node(step_id="s2")
        # Directly test _compile_colocation with no colocation_params
        node = PlanStepNode(
            search_name="bool",
            primary_input=left,
            secondary_input=right,
            operator=CombineOp.COLOCATE,
            colocation_params=None,
            id="c1",
        )
        compiler = StrategyCompiler(api, resolve_record_type=False)
        await compiler._compile_colocation(node, 100, 101, "gene")
        call_kwargs = api.create_transform_step.call_args.kwargs
        params = call_kwargs["parameters"]
        assert "upstream" not in params
        assert "downstream" not in params


# ---------------------------------------------------------------------------
# StrategyCompiler — record type resolution
# ---------------------------------------------------------------------------


class TestResolveRecordType:
    async def test_resolves_when_single_match(self) -> None:
        """Callback resolves search to a different record type."""
        api = _mock_api()
        api.create_step.return_value = {"id": 100}

        async def resolver(search_name: str) -> str | None:
            return "gene" if search_name == "GenesByTextSearch" else None

        step = _search_node()
        strategy = StrategyAST(record_type="transcript", root=step)

        compiler = StrategyCompiler(
            api, resolve_record_type=True, resolve_search_record_type=resolver
        )
        await compiler.compile(strategy)
        assert strategy.record_type == "gene"

    async def test_skips_resolution_when_disabled(self) -> None:
        api = _mock_api()
        api.create_step.return_value = {"id": 100}

        step = _search_node()
        strategy = StrategyAST(record_type="transcript", root=step)

        compiler = StrategyCompiler(api, resolve_record_type=False)
        await compiler.compile(strategy)

        assert strategy.record_type == "transcript"

    async def test_resolves_to_common_record_type(self) -> None:
        """When all leaf searches resolve to the same type, use it."""
        api = _mock_api()
        api.create_step.return_value = {"id": 100}
        api.create_combined_step.return_value = {"id": 200}

        async def resolver(search_name: str) -> str | None:
            # Both searches are on transcript
            return "transcript"

        left = _search_node(step_id="s1", search_name="GenesByTextSearch")
        right = _search_node(step_id="s2", search_name="GenesByGoTerm")
        root = _combine_node(left, right, step_id="c1")
        strategy = StrategyAST(record_type="gene", root=root)

        compiler = StrategyCompiler(
            api, resolve_record_type=True, resolve_search_record_type=resolver
        )
        await compiler.compile(strategy)
        assert strategy.record_type == "transcript"

    async def test_no_callback_keeps_original(self) -> None:
        """Without a callback, strategy keeps its original record type."""
        api = _mock_api()
        api.create_step.return_value = {"id": 100}

        step = _search_node()
        strategy = StrategyAST(record_type="gene", root=step)

        compiler = StrategyCompiler(api, resolve_record_type=True)
        await compiler.compile(strategy)
        assert strategy.record_type == "gene"

    async def test_callback_returns_none_keeps_original(self) -> None:
        """When callback can't resolve, strategy keeps original record type."""
        api = _mock_api()
        api.create_step.return_value = {"id": 100}

        async def resolver(search_name: str) -> str | None:
            return None

        step = _search_node()
        strategy = StrategyAST(record_type="gene", root=step)

        compiler = StrategyCompiler(
            api, resolve_record_type=True, resolve_search_record_type=resolver
        )
        await compiler.compile(strategy)
        assert strategy.record_type == "gene"

    async def test_per_step_resolution_for_transforms(self) -> None:
        """Transforms can resolve to a different record type than the strategy."""
        api = _mock_api()
        api.create_step.return_value = {"id": 100}
        api.create_transform_step.return_value = {"id": 300}

        async def resolver(search_name: str) -> str | None:
            if search_name == "GenesByTextSearch":
                return "gene"
            if search_name == "GenesByOrthologs":
                return "transcript"
            return None

        leaf = _search_node(step_id="s1", search_name="GenesByTextSearch")
        transform = PlanStepNode(
            search_name="GenesByOrthologs",
            parameters={"organism": "Pf3D7"},
            primary_input=leaf,
            id="t1",
        )
        strategy = StrategyAST(record_type="gene", root=transform)

        compiler = StrategyCompiler(
            api, resolve_record_type=True, resolve_search_record_type=resolver
        )
        await compiler.compile(strategy)

        # Transform's create_transform_step should have been called with record_type="transcript"
        call_kwargs = api.create_transform_step.call_args.kwargs
        assert call_kwargs["record_type"] == "transcript"


# ---------------------------------------------------------------------------
# StrategyCompiler — parameter coercion
# ---------------------------------------------------------------------------


class TestCoerceParameters:
    async def test_raises_on_metadata_load_failure(self) -> None:
        api = _mock_api()
        api.client.get_search_details.side_effect = Exception("404 Not Found")

        compiler = StrategyCompiler(api, resolve_record_type=False)
        with pytest.raises(ValidationError, match="Failed to load search metadata"):
            await compiler._coerce_parameters("gene", "FakeSearch", {"x": "1"})

    async def test_retries_with_context_on_validation_error(self) -> None:
        """When normalization fails, compiler retries with contextParamValues."""
        api = _mock_api()
        # First call returns spec that causes validation error
        api.client.get_search_details.return_value = {
            "searchData": {
                "parameters": [
                    {"name": "organism", "type": "single-pick-vocabulary"},
                    {"name": "text_expression", "type": "string"},
                ],
            },
        }
        # Second call with params provides richer spec
        api.client.get_search_details_with_params.return_value = {
            "searchData": {
                "parameters": [
                    {"name": "organism", "type": "string"},
                    {"name": "text_expression", "type": "string"},
                ],
            },
        }

        compiler = StrategyCompiler(api, resolve_record_type=False)
        result = await compiler._coerce_parameters(
            "gene",
            "GenesByTextSearch",
            {"organism": "Plasmodium", "text_expression": "kinase"},
        )
        assert "text_expression" in result

    async def test_input_step_param_cleared(self) -> None:
        """Input step params should be set to empty string."""
        api = _mock_api()
        api.client.get_search_details.return_value = {
            "searchData": {
                "parameters": [
                    {"name": "answer", "type": "input-step"},
                    {"name": "taxon", "type": "string"},
                ],
            },
        }

        compiler = StrategyCompiler(api, resolve_record_type=False)
        result = await compiler._coerce_parameters(
            "gene", "GenesByOrthology", {"taxon": "Plasmodium"}
        )
        assert result["answer"] == ""

    async def test_dataset_param_upload(self) -> None:
        """When a dataset param has raw IDs, they should be uploaded."""
        api = _mock_api()
        api.client.get_search_details.return_value = {
            "searchData": {
                "parameters": [
                    {"name": "ds_gene_ids", "type": "input-dataset"},
                ],
            },
        }
        api.create_dataset.return_value = 42

        compiler = StrategyCompiler(api, resolve_record_type=False)
        result = await compiler._coerce_parameters(
            "gene", "GenesByDataset", {"ds_gene_ids": "PF3D7_0100100,PF3D7_0100200"}
        )
        assert result["ds_gene_ids"] == "42"
        api.create_dataset.assert_awaited_once()
        # Verify the IDs were split properly
        call_args = api.create_dataset.call_args
        uploaded_ids = call_args[0][0]
        assert "PF3D7_0100100" in uploaded_ids
        assert "PF3D7_0100200" in uploaded_ids

    async def test_dataset_param_integer_no_upload(self) -> None:
        """When dataset param is already an integer ID, skip upload."""
        api = _mock_api()
        api.client.get_search_details.return_value = {
            "searchData": {
                "parameters": [
                    {"name": "ds_gene_ids", "type": "input-dataset"},
                ],
            },
        }

        compiler = StrategyCompiler(api, resolve_record_type=False)
        await compiler._coerce_parameters(
            "gene", "GenesByDataset", {"ds_gene_ids": "123"}
        )
        api.create_dataset.assert_not_awaited()

    async def test_unwraps_search_data(self) -> None:
        """Details wrapped in searchData should be unwrapped."""
        api = _mock_api()
        api.client.get_search_details.return_value = {
            "searchData": {
                "parameters": [
                    {"name": "text_expression", "type": "string"},
                ],
            },
        }

        compiler = StrategyCompiler(api, resolve_record_type=False)
        result = await compiler._coerce_parameters(
            "gene", "GenesByTextSearch", {"text_expression": "kinase"}
        )
        assert result["text_expression"] == "kinase"


# ---------------------------------------------------------------------------
# StrategyCompiler — root step failure
# ---------------------------------------------------------------------------


class TestCompileRootFailure:
    async def test_missing_root_compiled_step_raises(self) -> None:
        """If root step compilation doesn't register, should raise InternalError."""
        api = _mock_api()
        # Create a step that returns an ID but manipulate _compiled_steps to be empty
        api.create_step.return_value = {"id": 100}

        step = _search_node()
        strategy = StrategyAST(record_type="gene", root=step)

        compiler = StrategyCompiler(api, resolve_record_type=False)
        # Override _compile_node to not register the step
        original_compile_search = compiler._compile_search

        async def broken_compile_search(s: PlanStepNode, rt: str) -> StepTreeNode:
            tree = await original_compile_search(s, rt)
            # Remove the step from compiled_steps to simulate failure
            compiler._compiled_steps.clear()
            return tree

        compiler._compile_search = broken_compile_search
        with pytest.raises(InternalError, match="compilation failed"):
            await compiler.compile(strategy)


# ---------------------------------------------------------------------------
# apply_step_decorations
# ---------------------------------------------------------------------------


class TestApplyStepDecorations:
    async def test_applies_filters(self) -> None:
        api = _mock_api()
        step = _search_node()
        step.filters = [StepFilter(name="ranked", value=5, disabled=False)]
        strategy = StrategyAST(record_type="gene", root=step)
        compiled_map = {"s1": 100}

        await apply_step_decorations(strategy, compiled_map, api)

        api.set_step_filter.assert_awaited_once_with(
            step_id=100,
            filter_name="ranked",
            value=5,
            disabled=False,
        )

    async def test_applies_analyses(self) -> None:
        api = _mock_api()
        step = _search_node()
        step.analyses = [
            StepAnalysis(
                analysis_type="go-enrichment",
                parameters={"ontology": "biological_process"},
                custom_name="GO enrichment",
            ),
        ]
        strategy = StrategyAST(record_type="gene", root=step)
        compiled_map = {"s1": 100}

        await apply_step_decorations(strategy, compiled_map, api)

        api.run_step_analysis.assert_awaited_once_with(
            step_id=100,
            analysis_type="go-enrichment",
            parameters={"ontology": "biological_process"},
            custom_name="GO enrichment",
        )

    async def test_applies_reports(self) -> None:
        api = _mock_api()
        step = _search_node()
        step.reports = [StepReport(report_name="tabular", config={"format": "csv"})]
        strategy = StrategyAST(record_type="gene", root=step)
        compiled_map = {"s1": 100}

        await apply_step_decorations(strategy, compiled_map, api)

        api.run_step_report.assert_awaited_once_with(
            step_id=100,
            report_name="tabular",
            config={"format": "csv"},
        )

    async def test_skips_unmapped_steps(self) -> None:
        api = _mock_api()
        step = _search_node()
        step.filters = [StepFilter(name="ranked", value=5)]
        strategy = StrategyAST(record_type="gene", root=step)
        compiled_map = {}  # empty — no mapping

        await apply_step_decorations(strategy, compiled_map, api)

        api.set_step_filter.assert_not_awaited()

    async def test_applies_to_all_steps_in_tree(self) -> None:
        api = _mock_api()
        left = _search_node(step_id="s1")
        left.filters = [StepFilter(name="f1", value=1)]
        right = _search_node(step_id="s2")
        right.filters = [StepFilter(name="f2", value=2)]
        root = _combine_node(left, right)
        root.reports = [StepReport(report_name="standard")]
        strategy = StrategyAST(record_type="gene", root=root)
        compiled_map = {"s1": 100, "s2": 101, "c1": 200}

        await apply_step_decorations(strategy, compiled_map, api)

        assert api.set_step_filter.await_count == 2
        assert api.run_step_report.await_count == 1

    async def test_no_decorations_is_noop(self) -> None:
        api = _mock_api()
        step = _search_node()
        strategy = StrategyAST(record_type="gene", root=step)
        compiled_map = {"s1": 100}

        await apply_step_decorations(strategy, compiled_map, api)

        api.set_step_filter.assert_not_awaited()
        api.run_step_analysis.assert_not_awaited()
        api.run_step_report.assert_not_awaited()


# ---------------------------------------------------------------------------
# compile_strategy (convenience wrapper)
# ---------------------------------------------------------------------------


class TestCompileStrategyWrapper:
    async def test_delegates_to_compiler(self) -> None:
        api = _mock_api()
        api.create_step.return_value = {"id": 100}

        step = _search_node()
        strategy = StrategyAST(record_type="gene", root=step)
        result = await compile_strategy(strategy, api, resolve_record_type=False)

        assert isinstance(result, CompilationResult)
        assert result.root_step_id == 100


# ---------------------------------------------------------------------------
# Deep tree compilation
# ---------------------------------------------------------------------------


class TestDeepTree:
    async def test_three_level_tree(self) -> None:
        """Compile a tree: combine(search, transform(search))."""
        api = _mock_api()
        call_count = 0

        async def next_step_id(**kw: object) -> dict:
            nonlocal call_count
            call_count += 1
            return {"id": call_count * 100}

        api.create_step.side_effect = next_step_id
        api.create_transform_step.side_effect = next_step_id
        api.create_combined_step.side_effect = next_step_id

        s1 = _search_node(step_id="s1")
        s2 = _search_node(step_id="s2")
        t1 = _transform_node(s2, step_id="t1")
        root = _combine_node(s1, t1, step_id="c1")

        strategy = StrategyAST(record_type="gene", root=root)
        compiler = StrategyCompiler(api, resolve_record_type=False)
        result = await compiler.compile(strategy)

        assert len(result.steps) == 4
        # Verify tree structure
        assert result.step_tree.primary_input is not None
        assert result.step_tree.secondary_input is not None
        assert result.step_tree.secondary_input.primary_input is not None

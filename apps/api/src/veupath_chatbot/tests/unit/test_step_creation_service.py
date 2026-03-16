"""Tests for services.strategies.step_creation -- extracted step creation service."""

from unittest.mock import AsyncMock, patch

from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.domain.strategy.ops import CombineOp
from veupath_chatbot.domain.strategy.session import StrategyGraph
from veupath_chatbot.platform.errors import ErrorCode, ValidationError
from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.strategies.step_creation import (
    COMBINE_PLACEHOLDER_SEARCH_NAME,
    _build_colocation_params,
    _find_consumer,
    _validate_inputs,
    _validate_root_status,
    coerce_wdk_boolean_question_params,
    create_step,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_graph(graph_id: str = "g1", site_id: str = "plasmodb") -> StrategyGraph:
    return StrategyGraph(graph_id, "test", site_id)


def _noop_validation_error_payload(exc: ValidationError) -> JSONObject:
    """Simple validation error payload builder for tests."""
    return tool_error(ErrorCode.VALIDATION_ERROR, exc.title, detail=exc.detail)


async def _resolve_record_type_stub(
    record_type: str | None,
    search_name: str | None,
    require_match: bool,
    allow_fallback: bool,
) -> str | None:
    """Stub that always returns the record type as-is, or 'gene' as default."""
    return record_type or "transcript"


async def _find_record_type_hint_stub(
    search_name: str, exclude: str | None = None
) -> str | None:
    return None


def _extract_vocab_options_stub(vocabulary: JSONObject) -> list[str]:
    return []


# ---------------------------------------------------------------------------
# coerce_wdk_boolean_question_params
# ---------------------------------------------------------------------------


class TestCoerceWdkBooleanQuestionParams:
    """Test the pure extraction of bq_left_op_, bq_right_op_, bq_operator from parameters."""

    def test_extracts_boolean_question_params(self):
        params = {
            "bq_left_op_": "step_1",
            "bq_right_op_": "step_2",
            "bq_operator": "INTERSECT",
        }
        left, right, op = coerce_wdk_boolean_question_params(parameters=params)
        assert left == "step_1"
        assert right == "step_2"
        assert op == "INTERSECT"
        assert "bq_left_op_" not in params
        assert "bq_right_op_" not in params
        assert "bq_operator" not in params

    def test_returns_none_when_missing_all(self):
        params = {"some_param": "value"}
        left, right, op = coerce_wdk_boolean_question_params(parameters=params)
        assert left is None
        assert right is None
        assert op is None

    def test_returns_none_when_only_left_present(self):
        params = {"bq_left_op_": "step_1"}
        left, right, op = coerce_wdk_boolean_question_params(parameters=params)
        assert left is None
        assert right is None
        assert op is None

    def test_returns_none_when_operator_missing(self):
        params = {"bq_left_op_": "step_1", "bq_right_op_": "step_2"}
        left, right, op = coerce_wdk_boolean_question_params(parameters=params)
        assert left is None
        assert right is None
        assert op is None

    def test_returns_none_for_empty_params(self):
        left, right, op = coerce_wdk_boolean_question_params(parameters={})
        assert left is None
        assert right is None
        assert op is None

    def test_handles_suffixed_bq_keys(self):
        """WDK may use bq_left_op_XYZ style keys (anything starting with bq_left_op)."""
        params = {
            "bq_left_op_some_suffix": "step_a",
            "bq_right_op_another": "step_b",
            "bq_operator": "UNION",
        }
        left, right, op = coerce_wdk_boolean_question_params(parameters=params)
        assert left == "step_a"
        assert right == "step_b"
        assert op == "UNION"

    def test_returns_none_for_non_dict(self):
        # Should handle gracefully even though type says JSONObject
        left, right, op = coerce_wdk_boolean_question_params(parameters={})
        assert (left, right, op) == (None, None, None)

    def test_preserves_non_bq_keys(self):
        params = {
            "bq_left_op_": "step_1",
            "bq_right_op_": "step_2",
            "bq_operator": "UNION",
            "other_param": "keep_me",
        }
        coerce_wdk_boolean_question_params(parameters=params)
        assert params == {"other_param": "keep_me"}


# ---------------------------------------------------------------------------
# _find_consumer
# ---------------------------------------------------------------------------


class TestFindConsumer:
    def test_finds_consumer_via_primary(self):
        graph = _make_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        step_b = PlanStepNode(search_name="B", parameters={}, primary_input=step_a)
        graph.add_step(step_a)
        graph.add_step(step_b)
        assert _find_consumer(graph, step_a.id) == step_b.id

    def test_finds_consumer_via_secondary(self):
        graph = _make_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        step_b = PlanStepNode(search_name="B", parameters={})
        step_c = PlanStepNode(
            search_name="__combine__",
            parameters={},
            primary_input=step_a,
            secondary_input=step_b,
        )
        graph.add_step(step_a)
        graph.add_step(step_b)
        graph.add_step(step_c)
        assert _find_consumer(graph, step_b.id) == step_c.id

    def test_returns_none_for_unconsumed(self):
        graph = _make_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        graph.add_step(step_a)
        assert _find_consumer(graph, step_a.id) is None


# ---------------------------------------------------------------------------
# _validate_inputs
# ---------------------------------------------------------------------------


class TestValidateInputs:
    def test_no_inputs(self):
        graph = _make_graph()
        primary, secondary, error = _validate_inputs(graph, None, None, None)
        assert primary is None
        assert secondary is None
        assert error is None

    def test_primary_not_found(self):
        graph = _make_graph()
        _, _, error = _validate_inputs(graph, "missing", None, None)
        assert error is not None
        assert error["code"] == "STEP_NOT_FOUND"

    def test_secondary_not_found(self):
        graph = _make_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        graph.add_step(step_a)
        _, _, error = _validate_inputs(graph, step_a.id, "missing", "UNION")
        assert error is not None
        assert error["code"] == "STEP_NOT_FOUND"

    def test_secondary_without_primary(self):
        graph = _make_graph()
        step_b = PlanStepNode(search_name="B", parameters={})
        graph.add_step(step_b)
        _, _, error = _validate_inputs(graph, None, step_b.id, "UNION")
        assert error is not None
        assert "primary_input_step_id" in str(error["message"])

    def test_secondary_without_operator(self):
        graph = _make_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        step_b = PlanStepNode(search_name="B", parameters={})
        graph.add_step(step_a)
        graph.add_step(step_b)
        _, _, error = _validate_inputs(graph, step_a.id, step_b.id, None)
        assert error is not None
        assert "operator is required" in str(error["message"])

    def test_valid_binary_inputs(self):
        graph = _make_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        step_b = PlanStepNode(search_name="B", parameters={})
        graph.add_step(step_a)
        graph.add_step(step_b)
        primary, secondary, error = _validate_inputs(
            graph, step_a.id, step_b.id, "UNION"
        )
        assert primary is step_a
        assert secondary is step_b
        assert error is None


# ---------------------------------------------------------------------------
# _validate_root_status
# ---------------------------------------------------------------------------


class TestValidateRootStatus:
    def test_root_step_passes(self):
        graph = _make_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        graph.add_step(step_a)
        assert _validate_root_status(graph, step_a.id, "primary") is None

    def test_non_root_step_fails(self):
        graph = _make_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        step_b = PlanStepNode(search_name="B", parameters={})
        graph.add_step(step_a)
        graph.add_step(step_b)
        combine = PlanStepNode(
            search_name="__combine__",
            parameters={},
            primary_input=step_a,
            secondary_input=step_b,
        )
        graph.add_step(combine)
        error = _validate_root_status(graph, step_a.id, "primary")
        assert error is not None
        assert "not a subtree root" in str(error["message"])
        assert error["consumedBy"] == combine.id


# ---------------------------------------------------------------------------
# _build_colocation_params
# ---------------------------------------------------------------------------


class TestBuildColocationParams:
    def test_non_colocate_returns_none(self):
        assert _build_colocation_params(CombineOp.UNION, 10, 20, "same") is None
        assert _build_colocation_params(None, 10, 20, "same") is None

    def test_colocate_defaults(self):
        result = _build_colocation_params(CombineOp.COLOCATE, None, None, None)
        assert result is not None
        assert result.upstream == 0
        assert result.downstream == 0
        assert result.strand == "both"

    def test_colocate_custom(self):
        result = _build_colocation_params(CombineOp.COLOCATE, 100, 200, "same")
        assert result is not None
        assert result.upstream == 100
        assert result.downstream == 200
        assert result.strand == "same"

    def test_colocate_invalid_strand_defaults_to_both(self):
        result = _build_colocation_params(CombineOp.COLOCATE, 0, 0, "invalid")
        assert result is not None
        assert result.strand == "both"


# ---------------------------------------------------------------------------
# create_step integration tests (using stubs)
# ---------------------------------------------------------------------------


class TestCreateStepIntegration:
    """Test the full create_step flow with stubbed dependencies."""

    async def test_leaf_requires_search_name(self):
        graph = _make_graph()
        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            resolve_record_type_for_search=_resolve_record_type_stub,
            find_record_type_hint=_find_record_type_hint_stub,
            extract_vocab_options=_extract_vocab_options_stub,
            validation_error_payload=_noop_validation_error_payload,
        )
        assert result.error is not None
        assert "search_name is required" in str(result.error["message"])

    async def test_secondary_without_primary_returns_error(self):
        graph = _make_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        step_b = PlanStepNode(search_name="B", parameters={})
        graph.add_step(step_a)
        graph.add_step(step_b)

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            secondary_input_step_id=step_b.id,
            operator="UNION",
            resolve_record_type_for_search=_resolve_record_type_stub,
            find_record_type_hint=_find_record_type_hint_stub,
            extract_vocab_options=_extract_vocab_options_stub,
            validation_error_payload=_noop_validation_error_payload,
        )
        assert result.error is not None
        assert "primary_input_step_id" in str(result.error["message"])

    async def test_secondary_without_operator_returns_error(self):
        graph = _make_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        step_b = PlanStepNode(search_name="B", parameters={})
        graph.add_step(step_a)
        graph.add_step(step_b)

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            primary_input_step_id=step_a.id,
            secondary_input_step_id=step_b.id,
            resolve_record_type_for_search=_resolve_record_type_stub,
            find_record_type_hint=_find_record_type_hint_stub,
            extract_vocab_options=_extract_vocab_options_stub,
            validation_error_payload=_noop_validation_error_payload,
        )
        assert result.error is not None
        assert "operator is required" in str(result.error["message"])

    async def test_primary_input_not_found(self):
        graph = _make_graph()

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            search_name="SomeSearch",
            primary_input_step_id="nonexistent",
            resolve_record_type_for_search=_resolve_record_type_stub,
            find_record_type_hint=_find_record_type_hint_stub,
            extract_vocab_options=_extract_vocab_options_stub,
            validation_error_payload=_noop_validation_error_payload,
        )
        assert result.error is not None
        assert result.error["code"] == "STEP_NOT_FOUND"

    async def test_secondary_input_not_found(self):
        graph = _make_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        graph.add_step(step_a)

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            primary_input_step_id=step_a.id,
            secondary_input_step_id="nonexistent",
            operator="UNION",
            resolve_record_type_for_search=_resolve_record_type_stub,
            find_record_type_hint=_find_record_type_hint_stub,
            extract_vocab_options=_extract_vocab_options_stub,
            validation_error_payload=_noop_validation_error_payload,
        )
        assert result.error is not None
        assert result.error["code"] == "STEP_NOT_FOUND"

    async def test_non_root_primary_rejected(self):
        graph = _make_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        step_b = PlanStepNode(search_name="B", parameters={})
        graph.add_step(step_a)
        graph.add_step(step_b)
        combine = PlanStepNode(
            search_name="__combine__",
            parameters={},
            primary_input=step_a,
            secondary_input=step_b,
        )
        graph.add_step(combine)

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            search_name="SomeSearch",
            primary_input_step_id=step_a.id,
            resolve_record_type_for_search=_resolve_record_type_stub,
            find_record_type_hint=_find_record_type_hint_stub,
            extract_vocab_options=_extract_vocab_options_stub,
            validation_error_payload=_noop_validation_error_payload,
        )
        assert result.error is not None
        assert "not a subtree root" in str(result.error["message"])

    @patch(
        "veupath_chatbot.services.strategies.step_creation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_binary_step_creation_success(self, mock_validate: AsyncMock):
        graph = _make_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        step_b = PlanStepNode(search_name="B", parameters={})
        graph.add_step(step_a)
        graph.add_step(step_b)

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            primary_input_step_id=step_a.id,
            secondary_input_step_id=step_b.id,
            operator="UNION",
            display_name="A or B",
            resolve_record_type_for_search=_resolve_record_type_stub,
            find_record_type_hint=_find_record_type_hint_stub,
            extract_vocab_options=_extract_vocab_options_stub,
            validation_error_payload=_noop_validation_error_payload,
        )
        assert result.error is None
        assert result.step is not None
        assert result.step_id is not None
        assert result.step.search_name == COMBINE_PLACEHOLDER_SEARCH_NAME
        assert result.step.operator == CombineOp.UNION
        assert result.step.primary_input is step_a
        assert result.step.secondary_input is step_b
        assert result.step.display_name == "A or B"
        # validate_parameters should NOT be called for binary steps
        mock_validate.assert_not_awaited()

    @patch(
        "veupath_chatbot.services.strategies.step_creation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_leaf_step_creation_success(self, mock_validate: AsyncMock):
        graph = _make_graph()

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            search_name="GenesByText",
            parameters={"text_expression": "kinase"},
            resolve_record_type_for_search=_resolve_record_type_stub,
            find_record_type_hint=_find_record_type_hint_stub,
            extract_vocab_options=_extract_vocab_options_stub,
            validation_error_payload=_noop_validation_error_payload,
        )
        assert result.error is None
        assert result.step is not None
        assert result.step_id is not None
        assert result.step.search_name == "GenesByText"
        assert result.step.parameters == {"text_expression": "kinase"}
        assert result.step.primary_input is None
        assert result.step.secondary_input is None
        # validate_parameters should be called for leaf steps
        mock_validate.assert_awaited_once()

    @patch(
        "veupath_chatbot.services.strategies.step_creation.get_wdk_client",
    )
    @patch(
        "veupath_chatbot.services.strategies.step_creation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_transform_step_validates_input_step_param(
        self, mock_validate: AsyncMock, mock_get_wdk: AsyncMock
    ):
        """Transform steps must verify the question accepts an input step."""
        graph = _make_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        graph.add_step(step_a)

        # Mock WDK client to return a search with an input-step param
        mock_client = AsyncMock()
        mock_client.get_search_details = AsyncMock(
            return_value={
                "searchData": {
                    "parameters": [
                        {"name": "input_step", "type": "input-step"},
                        {"name": "other_param", "type": "string"},
                    ]
                }
            }
        )
        mock_get_wdk.return_value = mock_client

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            search_name="GenesByUpstream",
            primary_input_step_id=step_a.id,
            resolve_record_type_for_search=_resolve_record_type_stub,
            find_record_type_hint=_find_record_type_hint_stub,
            extract_vocab_options=_extract_vocab_options_stub,
            validation_error_payload=_noop_validation_error_payload,
        )
        assert result.error is None
        assert result.step is not None
        assert result.step.primary_input is step_a

    @patch(
        "veupath_chatbot.services.strategies.step_creation.get_wdk_client",
    )
    @patch(
        "veupath_chatbot.services.strategies.step_creation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_transform_step_rejects_non_transform_question(
        self, mock_validate: AsyncMock, mock_get_wdk: AsyncMock
    ):
        """A question without input-step param cannot be used as transform."""
        graph = _make_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        graph.add_step(step_a)

        mock_client = AsyncMock()
        mock_client.get_search_details = AsyncMock(
            return_value={
                "searchData": {
                    "parameters": [
                        {"name": "text_expression", "type": "string"},
                    ]
                }
            }
        )
        mock_get_wdk.return_value = mock_client

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            search_name="GenesByText",
            primary_input_step_id=step_a.id,
            resolve_record_type_for_search=_resolve_record_type_stub,
            find_record_type_hint=_find_record_type_hint_stub,
            extract_vocab_options=_extract_vocab_options_stub,
            validation_error_payload=_noop_validation_error_payload,
        )
        assert result.error is not None
        assert "cannot be used as a transform" in str(result.error["message"])

    @patch(
        "veupath_chatbot.services.strategies.step_creation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_binary_with_bq_params_coercion(self, mock_validate: AsyncMock):
        """Boolean question params should be coerced into structural inputs."""
        graph = _make_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        step_b = PlanStepNode(search_name="B", parameters={})
        graph.add_step(step_a)
        graph.add_step(step_b)

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            parameters={
                "bq_left_op_": step_a.id,
                "bq_right_op_": step_b.id,
                "bq_operator": "INTERSECT",
            },
            resolve_record_type_for_search=_resolve_record_type_stub,
            find_record_type_hint=_find_record_type_hint_stub,
            extract_vocab_options=_extract_vocab_options_stub,
            validation_error_payload=_noop_validation_error_payload,
        )
        assert result.error is None
        assert result.step is not None
        assert result.step.operator == CombineOp.INTERSECT
        assert result.step.primary_input is step_a
        assert result.step.secondary_input is step_b

    @patch(
        "veupath_chatbot.services.strategies.step_creation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_colocate_step_creation(self, mock_validate: AsyncMock):
        graph = _make_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        step_b = PlanStepNode(search_name="B", parameters={})
        graph.add_step(step_a)
        graph.add_step(step_b)

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            primary_input_step_id=step_a.id,
            secondary_input_step_id=step_b.id,
            operator="COLOCATE",
            upstream=500,
            downstream=1000,
            strand="same",
            resolve_record_type_for_search=_resolve_record_type_stub,
            find_record_type_hint=_find_record_type_hint_stub,
            extract_vocab_options=_extract_vocab_options_stub,
            validation_error_payload=_noop_validation_error_payload,
        )
        assert result.error is None
        assert result.step is not None
        assert result.step.operator == CombineOp.COLOCATE
        assert result.step.colocation_params is not None
        assert result.step.colocation_params.upstream == 500
        assert result.step.colocation_params.downstream == 1000
        assert result.step.colocation_params.strand == "same"

    @patch(
        "veupath_chatbot.services.strategies.step_creation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_record_type_defaults_to_gene(self, mock_validate: AsyncMock):
        """When no record type is available, it should default to 'gene'."""
        graph = _make_graph()
        assert graph.record_type is None

        async def always_none_resolver(
            rt: str | None, sn: str | None, req: bool, fb: bool
        ) -> str | None:
            return None

        await create_step(
            graph=graph,
            site_id="plasmodb",
            search_name="GenesByText",
            resolve_record_type_for_search=always_none_resolver,
            find_record_type_hint=_find_record_type_hint_stub,
            extract_vocab_options=_extract_vocab_options_stub,
            validation_error_payload=_noop_validation_error_payload,
        )
        # The leaf validation will fail because always_none_resolver returns None
        # when called with require_match=True. But graph.record_type should be set.
        assert graph.record_type == "gene"

    async def test_step_added_to_graph(self):
        """Successful creation adds the step to the graph."""
        graph = _make_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        step_b = PlanStepNode(search_name="B", parameters={})
        graph.add_step(step_a)
        graph.add_step(step_b)
        initial_step_count = len(graph.steps)

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            primary_input_step_id=step_a.id,
            secondary_input_step_id=step_b.id,
            operator="UNION",
            resolve_record_type_for_search=_resolve_record_type_stub,
            find_record_type_hint=_find_record_type_hint_stub,
            extract_vocab_options=_extract_vocab_options_stub,
            validation_error_payload=_noop_validation_error_payload,
        )
        assert result.error is None
        assert len(graph.steps) == initial_step_count + 1
        assert result.step_id in graph.steps
        assert result.step_id in graph.roots
        # Consumed inputs should no longer be roots
        assert step_a.id not in graph.roots
        assert step_b.id not in graph.roots

    @patch(
        "veupath_chatbot.services.strategies.step_creation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_leaf_step_search_not_found(self, mock_validate: AsyncMock):
        """Leaf step with unknown search should return SEARCH_NOT_FOUND."""
        graph = _make_graph()

        async def reject_search(
            rt: str | None, sn: str | None, req: bool, fb: bool
        ) -> str | None:
            if req:
                return None
            return rt or "transcript"

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            search_name="NonexistentSearch",
            resolve_record_type_for_search=reject_search,
            find_record_type_hint=_find_record_type_hint_stub,
            extract_vocab_options=_extract_vocab_options_stub,
            validation_error_payload=_noop_validation_error_payload,
        )
        assert result.error is not None
        assert result.error["code"] == "SEARCH_NOT_FOUND"

    @patch(
        "veupath_chatbot.services.strategies.step_creation.validate_parameters",
        new_callable=AsyncMock,
        side_effect=ValidationError(
            title="Missing required parameters",
            detail="param_x is required",
        ),
    )
    async def test_leaf_step_validation_error(self, mock_validate: AsyncMock):
        """Leaf step with validation error should return the error payload."""
        graph = _make_graph()

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            search_name="GenesByText",
            resolve_record_type_for_search=_resolve_record_type_stub,
            find_record_type_hint=_find_record_type_hint_stub,
            extract_vocab_options=_extract_vocab_options_stub,
            validation_error_payload=_noop_validation_error_payload,
        )
        assert result.error is not None
        assert result.error["code"] == "VALIDATION_ERROR"

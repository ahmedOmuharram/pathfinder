"""Tests for services.strategies.step_creation -- extracted step creation service."""

from unittest.mock import AsyncMock, patch

import pydantic
import pytest

from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.domain.strategy.ops import ColocationParams, CombineOp
from veupath_chatbot.domain.strategy.organism import extract_output_organisms
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKSearchResponse
from veupath_chatbot.platform.errors import ValidationError
from veupath_chatbot.services.catalog.param_validation import ValidationCallbacks
from veupath_chatbot.services.strategies.step_creation import (
    COMBINE_PLACEHOLDER_SEARCH_NAME,
    InlineSpec,
    StepSpec,
    coerce_wdk_boolean_question_params,
    create_step,
    resolve_inline_step,
)
from veupath_chatbot.services.strategies.step_validation import (
    _validate_inputs,
)

from .conftest import (
    find_record_type_hint_stub,
    make_step_creation_callbacks,
    make_step_graph,
    noop_validation_error_payload,
    populate_graph,
)

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
        graph = make_step_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        step_b = PlanStepNode(search_name="B", parameters={}, primary_input=step_a)
        graph.add_step(step_a)
        graph.add_step(step_b)
        assert graph.find_consumer(step_a.id) == step_b.id

    def test_finds_consumer_via_secondary(self):
        graph = make_step_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        step_b = PlanStepNode(search_name="B", parameters={})
        step_c = PlanStepNode(
            search_name="__combine__",
            parameters={},
            primary_input=step_a,
            secondary_input=step_b,
            operator=CombineOp.INTERSECT,
        )
        populate_graph(graph, step_a, step_b, step_c)
        assert graph.find_consumer(step_b.id) == step_c.id

    def test_returns_none_for_unconsumed(self):
        graph = make_step_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        graph.add_step(step_a)
        assert graph.find_consumer(step_a.id) is None


# ---------------------------------------------------------------------------
# _validate_inputs
# ---------------------------------------------------------------------------


class TestValidateInputs:
    def test_no_inputs(self):
        graph = make_step_graph()
        primary, secondary, error = _validate_inputs(graph, None, None, None)
        assert primary is None
        assert secondary is None
        assert error is None

    def test_primary_not_found(self):
        graph = make_step_graph()
        _, _, error = _validate_inputs(graph, "missing", None, None)
        assert error is not None
        assert error["code"] == "STEP_NOT_FOUND"

    def test_secondary_not_found(self):
        graph = make_step_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        graph.add_step(step_a)
        _, _, error = _validate_inputs(graph, step_a.id, "missing", "UNION")
        assert error is not None
        assert error["code"] == "STEP_NOT_FOUND"

    def test_secondary_without_primary(self):
        graph = make_step_graph()
        step_b = PlanStepNode(search_name="B", parameters={})
        graph.add_step(step_b)
        _, _, error = _validate_inputs(graph, None, step_b.id, "UNION")
        assert error is not None
        assert "primary_input_step_id" in str(error["message"])

    def test_secondary_without_operator(self):
        graph = make_step_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        step_b = PlanStepNode(search_name="B", parameters={})
        populate_graph(graph, step_a, step_b)
        _, _, error = _validate_inputs(graph, step_a.id, step_b.id, None)
        assert error is not None
        assert "operator is required" in str(error["message"])

    def test_valid_binary_inputs(self):
        graph = make_step_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        step_b = PlanStepNode(search_name="B", parameters={})
        populate_graph(graph, step_a, step_b)
        primary, secondary, error = _validate_inputs(
            graph, step_a.id, step_b.id, "UNION"
        )
        assert primary is step_a
        assert secondary is step_b
        assert error is None


# ---------------------------------------------------------------------------
# Auto-duplication of consumed steps
# ---------------------------------------------------------------------------


class TestAutoDuplication:
    """Consumed steps are silently cloned when referenced as inputs."""

    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_binary_combine_with_consumed_primary(self, mock_validate: AsyncMock):
        """Referencing a consumed step as primary input of a binary combine
        should auto-duplicate it instead of erroring."""
        graph = make_step_graph()
        step_a = PlanStepNode(search_name="GenesByTaxon", parameters={"organism": '["Pf"]'})
        graph.add_step(step_a)
        # Transform consumes step_a.
        transform = PlanStepNode(
            search_name="GenesByOrthologs",
            parameters={},
            primary_input=step_a,
        )
        graph.add_step(transform)
        assert step_a.id not in graph.roots

        # Create a combine referencing consumed step_a + root transform.
        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                primary_input_step_id=step_a.id,
                secondary_input_step_id=transform.id,
                operator="MINUS",
            ),
            callbacks=make_step_creation_callbacks(),
        )
        assert result.error is None
        assert result.step is not None
        # Primary input is a CLONE, not the original step_a.
        assert result.step.primary_input is not step_a
        assert result.step.primary_input is not None
        assert result.step.primary_input.search_name == "GenesByTaxon"
        assert result.step.primary_input.parameters == {"organism": '["Pf"]'}
        # Secondary is the original transform.
        assert result.step.secondary_input is transform
        assert result.step.operator == CombineOp.MINUS

    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_duplicate_preserves_subtree(self, mock_validate: AsyncMock):
        """Auto-duplicating a transform step clones its entire subtree."""
        graph = make_step_graph()
        leaf = PlanStepNode(search_name="A", parameters={"x": "1"})
        graph.add_step(leaf)
        transform = PlanStepNode(
            search_name="Transform",
            parameters={},
            primary_input=leaf,
        )
        graph.add_step(transform)
        # transform is now the root, leaf is consumed.

        # Reference consumed leaf in a binary combine with root (transform).
        # This tests that the leaf's clone is a fresh node.
        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                primary_input_step_id=leaf.id,
                secondary_input_step_id=transform.id,
                operator="MINUS",
            ),
            callbacks=make_step_creation_callbacks(),
        )
        assert result.error is None
        assert result.step is not None
        cloned_leaf = result.step.primary_input
        assert cloned_leaf is not None
        assert cloned_leaf is not leaf
        assert cloned_leaf.search_name == "A"
        assert cloned_leaf.parameters == {"x": "1"}
        # Clone has a fresh ID.
        assert cloned_leaf.id != leaf.id


# ---------------------------------------------------------------------------
# Inline step specs (_skip_auto_combine)
# ---------------------------------------------------------------------------


class TestInlineStepSpec:
    """Inline steps bypass auto-combine and don't become roots."""

    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_skip_auto_combine_does_not_become_root(self, mock_validate: AsyncMock):
        """A step with _skip_auto_combine registers in graph.steps but not roots."""
        graph = make_step_graph()
        existing = PlanStepNode(search_name="Existing", parameters={})
        graph.add_step(existing)

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                search_name="InlineLeaf",
                parameters={},
                _skip_auto_combine=True,
            ),
            callbacks=make_step_creation_callbacks(),
        )
        assert result.error is None
        assert result.step_id is not None
        # Inline step is in graph.steps but NOT in roots.
        assert result.step_id in graph.steps
        assert result.step_id not in graph.roots
        # Original root is unchanged.
        assert existing.id in graph.roots

    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_resolve_inline_step(self, mock_validate: AsyncMock):
        """resolve_inline_step creates a step without auto-combine."""

        graph = make_step_graph()
        root = PlanStepNode(search_name="Root", parameters={})
        graph.add_step(root)

        result = await resolve_inline_step(
            graph=graph,
            site_id="plasmodb",
            spec=InlineSpec(search_name="InlineSearch", parameters={"k": "v"}),
            callbacks=make_step_creation_callbacks(),
        )
        assert result.error is None
        assert result.step_id is not None
        assert result.step_id in graph.steps
        assert result.step_id not in graph.roots
        assert root.id in graph.roots

    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_inline_transform_then_combine(self, mock_validate: AsyncMock):
        """Build combine(Transform(A), B) atomically using inline spec."""

        graph = make_step_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        graph.add_step(step_a)
        step_b = PlanStepNode(search_name="B", parameters={})
        graph.insert_step_with_combine(step_b, step_a.id, CombineOp.UNION)

        # Create inline transform on step_a (consumed).
        inline_result = await resolve_inline_step(
            graph=graph,
            site_id="plasmodb",
            spec=InlineSpec(
                search_name="GenesByOrthologs",
                primary_input_step_id=step_a.id,
            ),
            callbacks=make_step_creation_callbacks(),
        )
        assert inline_result.error is None
        inline_id = inline_result.step_id
        assert inline_id is not None
        # Inline step used auto-duplication for consumed step_a.
        inline_step = graph.steps[inline_id]
        assert inline_step.primary_input is not step_a  # it's a clone

        # Now combine inline transform with the current root.
        root_id = next(iter(graph.roots))
        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                primary_input_step_id=inline_id,
                secondary_input_step_id=root_id,
                operator="MINUS",
            ),
            callbacks=make_step_creation_callbacks(),
        )
        assert result.error is None
        assert result.step is not None
        assert result.step.operator == CombineOp.MINUS
        assert len(graph.roots) == 1


# ---------------------------------------------------------------------------
# _build_colocation_params
# ---------------------------------------------------------------------------


class TestBuildColocationParams:
    def test_defaults(self) -> None:
        params = ColocationParams()
        assert params.operation == "overlaps"
        assert params.strand == "either strand"
        assert params.begin_offset_a == 1000
        assert params.region_a == "custom"

    def test_custom_construction(self) -> None:
        params = ColocationParams(
            operation="contains",
            strand="same strand",
            region_a="upstream",
            begin_offset_a=100,
            end_offset_a=200,
        )
        assert params.operation == "contains"
        assert params.strand == "same strand"
        assert params.begin_offset_a == 100
        assert params.end_offset_a == 200

    def test_model_validate_from_dict(self) -> None:
        params = ColocationParams.model_validate(
            {"operation": "is contained in", "strand": "opposite strand"}
        )
        assert params.operation == "is contained in"
        assert params.strand == "opposite strand"

    def test_invalid_strand_rejected(self) -> None:
        with pytest.raises(pydantic.ValidationError):
            ColocationParams(strand="invalid")


# ---------------------------------------------------------------------------
# create_step integration tests (using stubs)
# ---------------------------------------------------------------------------


class TestCreateStepIntegration:
    """Test the full create_step flow with stubbed dependencies."""

    async def test_leaf_requires_search_name(self):
        graph = make_step_graph()
        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(),
            callbacks=make_step_creation_callbacks(),
        )
        assert result.error is not None
        assert "search_name is required" in str(result.error["message"])

    async def test_secondary_without_primary_returns_error(self):
        graph = make_step_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        step_b = PlanStepNode(search_name="B", parameters={})
        populate_graph(graph, step_a, step_b)

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(secondary_input_step_id=step_b.id, operator="UNION"),
            callbacks=make_step_creation_callbacks(),
        )
        assert result.error is not None
        assert "primary_input_step_id" in str(result.error["message"])

    async def test_secondary_without_operator_returns_error(self):
        graph = make_step_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        step_b = PlanStepNode(search_name="B", parameters={})
        populate_graph(graph, step_a, step_b)

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                primary_input_step_id=step_a.id,
                secondary_input_step_id=step_b.id,
            ),
            callbacks=make_step_creation_callbacks(),
        )
        assert result.error is not None
        assert "operator is required" in str(result.error["message"])

    async def test_primary_input_not_found(self):
        graph = make_step_graph()

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                search_name="SomeSearch", primary_input_step_id="nonexistent"
            ),
            callbacks=make_step_creation_callbacks(),
        )
        assert result.error is not None
        assert result.error["code"] == "STEP_NOT_FOUND"

    async def test_secondary_input_not_found(self):
        graph = make_step_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        graph.add_step(step_a)

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                primary_input_step_id=step_a.id,
                secondary_input_step_id="nonexistent",
                operator="UNION",
            ),
            callbacks=make_step_creation_callbacks(),
        )
        assert result.error is not None
        assert result.error["code"] == "STEP_NOT_FOUND"

    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_binary_step_creation_success(self, mock_validate: AsyncMock):
        graph = make_step_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        step_b = PlanStepNode(search_name="B", parameters={})
        populate_graph(graph, step_a, step_b)

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                primary_input_step_id=step_a.id,
                secondary_input_step_id=step_b.id,
                operator="UNION",
                display_name="A or B",
            ),
            callbacks=make_step_creation_callbacks(),
        )
        assert result.error is None
        assert result.step is not None
        assert result.step_id is not None
        assert result.step.search_name == COMBINE_PLACEHOLDER_SEARCH_NAME
        assert result.step.operator == CombineOp.UNION
        assert result.step.primary_input is step_a
        assert result.step.secondary_input is step_b
        assert result.step.display_name == "A or B"

    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_leaf_step_creation_success(self, mock_validate: AsyncMock):
        graph = make_step_graph()

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                search_name="GenesByText",
                parameters={"text_expression": "kinase"},
            ),
            callbacks=make_step_creation_callbacks(),
        )
        assert result.error is None
        assert result.step is not None
        assert result.step_id is not None
        assert result.step.search_name == "GenesByText"
        assert result.step.parameters == {"text_expression": "kinase"}
        assert result.step.primary_input is None
        assert result.step.secondary_input is None

    @patch(
        "veupath_chatbot.services.strategies.step_validation.get_wdk_client",
    )
    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_transform_step_validates_input_step_param(
        self, mock_validate: AsyncMock, mock_get_wdk: AsyncMock
    ):
        """Transform steps must verify the question accepts an input step."""
        graph = make_step_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        graph.add_step(step_a)

        # Mock WDK client to return a search with an input-step param
        mock_client = AsyncMock()
        mock_client.get_search_details = AsyncMock(
            return_value=WDKSearchResponse.model_validate(
                {
                    "searchData": {
                        "urlSegment": "GenesByUpstream",
                        "parameters": [
                            {"name": "input_step", "type": "input-step"},
                            {"name": "other_param", "type": "string"},
                        ],
                    },
                    "validation": {"level": "DISPLAYABLE", "isValid": True},
                }
            ),
        )
        mock_get_wdk.return_value = mock_client

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                search_name="GenesByUpstream",
                primary_input_step_id=step_a.id,
            ),
            callbacks=make_step_creation_callbacks(),
        )
        assert result.error is None
        assert result.step is not None
        assert result.step.primary_input is step_a

    @patch(
        "veupath_chatbot.services.strategies.step_validation.get_wdk_client",
    )
    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_transform_step_rejects_non_transform_question(
        self, mock_validate: AsyncMock, mock_get_wdk: AsyncMock
    ):
        """A question without input-step param cannot be used as transform."""
        graph = make_step_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        graph.add_step(step_a)

        mock_client = AsyncMock()
        mock_client.get_search_details = AsyncMock(
            return_value=WDKSearchResponse.model_validate(
                {
                    "searchData": {
                        "urlSegment": "GenesByText",
                        "parameters": [
                            {"name": "text_expression", "type": "string"},
                        ],
                    },
                    "validation": {"level": "DISPLAYABLE", "isValid": True},
                }
            ),
        )
        mock_get_wdk.return_value = mock_client

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                search_name="GenesByText",
                primary_input_step_id=step_a.id,
            ),
            callbacks=make_step_creation_callbacks(),
        )
        assert result.error is not None
        assert "cannot be used as a transform" in str(result.error["message"])

    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_binary_with_bq_params_coercion(self, mock_validate: AsyncMock):
        """Boolean question params should be coerced into structural inputs."""
        graph = make_step_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        step_b = PlanStepNode(search_name="B", parameters={})
        populate_graph(graph, step_a, step_b)

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                parameters={
                    "bq_left_op_": step_a.id,
                    "bq_right_op_": step_b.id,
                    "bq_operator": "INTERSECT",
                }
            ),
            callbacks=make_step_creation_callbacks(),
        )
        assert result.error is None
        assert result.step is not None
        assert result.step.operator == CombineOp.INTERSECT
        assert result.step.primary_input is step_a
        assert result.step.secondary_input is step_b

    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_colocate_step_creation(self, mock_validate: AsyncMock):
        graph = make_step_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        step_b = PlanStepNode(search_name="B", parameters={})
        populate_graph(graph, step_a, step_b)

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                primary_input_step_id=step_a.id,
                secondary_input_step_id=step_b.id,
                operator="COLOCATE",
                colocation_params=ColocationParams(
                    operation="contains",
                    strand="same strand",
                    begin_offset_a=500,
                    end_offset_a=1000,
                ),
            ),
            callbacks=make_step_creation_callbacks(),
        )
        assert result.error is None
        assert result.step is not None
        assert result.step.operator == CombineOp.COLOCATE
        assert result.step.colocation_params is not None
        assert result.step.colocation_params.operation == "contains"
        assert result.step.colocation_params.strand == "same strand"
        assert result.step.colocation_params.begin_offset_a == 500
        assert result.step.colocation_params.end_offset_a == 1000

    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_record_type_defaults_to_transcript(self, mock_validate: AsyncMock):
        """When no record type is available, it should default to 'transcript'."""
        graph = make_step_graph()
        assert graph.record_type is None

        async def always_none_resolver(
            record_type: str | None,
            search_name: str | None,
            *,
            require_match: bool = False,
            allow_fallback: bool = True,
        ) -> str | None:
            return None

        await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(search_name="GenesByText"),
            callbacks=ValidationCallbacks(
                resolve_record_type_for_search=always_none_resolver,
                find_record_type_hint=find_record_type_hint_stub,
                validation_error_payload=noop_validation_error_payload,
            ),
        )
        # The leaf validation will fail because always_none_resolver returns None
        # when called with require_match=True. But graph.record_type should be set.
        assert graph.record_type == "transcript"

    async def test_step_added_to_graph(self):
        """Successful creation adds the step to the graph."""
        graph = make_step_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        step_b = PlanStepNode(search_name="B", parameters={})
        populate_graph(graph, step_a, step_b)
        initial_step_count = len(graph.steps)

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                primary_input_step_id=step_a.id,
                secondary_input_step_id=step_b.id,
                operator="UNION",
            ),
            callbacks=make_step_creation_callbacks(),
        )
        assert result.error is None
        assert len(graph.steps) == initial_step_count + 1
        assert result.step_id in graph.steps
        assert result.step_id in graph.roots
        # Consumed inputs should no longer be roots
        assert step_a.id not in graph.roots
        assert step_b.id not in graph.roots

    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_leaf_step_search_not_found(self, mock_validate: AsyncMock):
        """Leaf step with unknown search should return SEARCH_NOT_FOUND."""
        graph = make_step_graph()

        async def reject_search(
            record_type: str | None,
            search_name: str | None,
            *,
            require_match: bool = False,
            allow_fallback: bool = True,
        ) -> str | None:
            if require_match:
                return None
            return record_type or "transcript"

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(search_name="NonexistentSearch"),
            callbacks=ValidationCallbacks(
                resolve_record_type_for_search=reject_search,
                find_record_type_hint=find_record_type_hint_stub,
                validation_error_payload=noop_validation_error_payload,
            ),
        )
        assert result.error is not None
        assert result.error["code"] == "SEARCH_NOT_FOUND"

    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
        side_effect=ValidationError(
            title="Missing required parameters",
            detail="param_x is required",
        ),
    )
    async def test_leaf_step_validation_error(self, mock_validate: AsyncMock):
        """Leaf step with validation error should return the error payload."""
        graph = make_step_graph()

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(search_name="GenesByText"),
            callbacks=make_step_creation_callbacks(),
        )
        assert result.error is not None
        assert result.error["code"] == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# extract_output_organisms
# ---------------------------------------------------------------------------


class TestExtractOutputOrganisms:
    """Tests for organism scope extraction from step subtrees."""

    def test_leaf_with_organism_param(self) -> None:
        step = PlanStepNode(
            search_name="GenesByGoTerm",
            parameters={"organism": '["Plasmodium falciparum 3D7"]'},
        )
        assert extract_output_organisms(step) == {"Plasmodium falciparum 3D7"}

    def test_leaf_with_text_search_organism(self) -> None:
        step = PlanStepNode(
            search_name="GenesByText",
            parameters={"text_search_organism": '["Plasmodium berghei ANKA"]'},
        )
        assert extract_output_organisms(step) == {"Plasmodium berghei ANKA"}

    def test_leaf_without_organism_returns_none(self) -> None:
        step = PlanStepNode(
            search_name="GenesByMassSpec",
            parameters={"ms_assay": '["merozoite_Plasmodium falciparum 3D7"]'},
        )
        assert extract_output_organisms(step) is None

    def test_orthologs_transform_returns_target_organism(self) -> None:
        inner = PlanStepNode(
            search_name="GenesByGoTerm",
            parameters={"organism": '["Plasmodium falciparum 3D7"]'},
        )
        ortho = PlanStepNode(
            search_name="GenesByOrthologs",
            parameters={"organism": '["Plasmodium berghei ANKA"]'},
            primary_input=inner,
        )
        # Output is Pb, not Pf — the transform changes the organism scope
        assert extract_output_organisms(ortho) == {"Plasmodium berghei ANKA"}

    def test_combine_inherits_from_primary(self) -> None:
        pf = PlanStepNode(
            search_name="GenesByGoTerm",
            parameters={"organism": '["Plasmodium falciparum 3D7"]'},
        )
        pf2 = PlanStepNode(
            search_name="GenesByText",
            parameters={"text_search_organism": '["Plasmodium falciparum 3D7"]'},
        )
        combine = PlanStepNode(
            search_name="__combine__",
            primary_input=pf,
            secondary_input=pf2,
            operator=CombineOp.UNION,
        )
        assert extract_output_organisms(combine) == {"Plasmodium falciparum 3D7"}

    def test_non_orthologs_transform_passthrough(self) -> None:
        inner = PlanStepNode(
            search_name="GenesByGoTerm",
            parameters={"organism": '["Plasmodium falciparum 3D7"]'},
        )
        transform = PlanStepNode(
            search_name="GenesByPathwaysTransform",
            parameters={},
            primary_input=inner,
        )
        assert extract_output_organisms(transform) == {"Plasmodium falciparum 3D7"}

    def test_multiple_organisms_in_param(self) -> None:
        step = PlanStepNode(
            search_name="GenesByGoTerm",
            parameters={
                "organism": '["Plasmodium falciparum 3D7", "Plasmodium vivax P01"]'
            },
        )
        result = extract_output_organisms(step)
        assert result == {"Plasmodium falciparum 3D7", "Plasmodium vivax P01"}


# ---------------------------------------------------------------------------
# Cross-organism INTERSECT guard
# ---------------------------------------------------------------------------


class TestCrossOrganismIntersectGuard:
    """Combining steps from different organisms with INTERSECT must fail."""

    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_intersect_different_organisms_rejected(
        self, mock_val: AsyncMock
    ) -> None:
        graph = make_step_graph()
        pf_step = PlanStepNode(
            search_name="GenesByGoTerm",
            parameters={"organism": '["Plasmodium falciparum 3D7"]'},
        )
        pb_step = PlanStepNode(
            search_name="GenesByText",
            parameters={"text_search_organism": '["Plasmodium berghei ANKA"]'},
        )
        populate_graph(graph, pf_step, pb_step)
        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                primary_input_step_id=pf_step.id,
                secondary_input_step_id=pb_step.id,
                operator="INTERSECT",
            ),
            callbacks=make_step_creation_callbacks(),
        )
        assert result.error is not None
        assert result.error["code"] == "INVALID_STRATEGY"
        assert "different organism" in str(result.error["message"]).lower()

    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_intersect_same_organism_allowed(self, mock_val: AsyncMock) -> None:
        graph = make_step_graph()
        step_a = PlanStepNode(
            search_name="GenesByGoTerm",
            parameters={"organism": '["Plasmodium falciparum 3D7"]'},
        )
        step_b = PlanStepNode(
            search_name="GenesByText",
            parameters={"text_search_organism": '["Plasmodium falciparum 3D7"]'},
        )
        populate_graph(graph, step_a, step_b)
        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                primary_input_step_id=step_a.id,
                secondary_input_step_id=step_b.id,
                operator="INTERSECT",
            ),
            callbacks=make_step_creation_callbacks(),
        )
        assert result.error is None
        assert result.step is not None

    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_union_different_organisms_allowed(self, mock_val: AsyncMock) -> None:
        """UNION across organisms is valid (e.g. collecting genes from multiple species)."""
        graph = make_step_graph()
        pf_step = PlanStepNode(
            search_name="GenesByGoTerm",
            parameters={"organism": '["Plasmodium falciparum 3D7"]'},
        )
        pb_step = PlanStepNode(
            search_name="GenesByText",
            parameters={"text_search_organism": '["Plasmodium berghei ANKA"]'},
        )
        populate_graph(graph, pf_step, pb_step)
        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                primary_input_step_id=pf_step.id,
                secondary_input_step_id=pb_step.id,
                operator="UNION",
            ),
            callbacks=make_step_creation_callbacks(),
        )
        assert result.error is None
        assert result.step is not None

    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_intersect_no_organism_param_skips_check(
        self, mock_val: AsyncMock
    ) -> None:
        """Steps without organism params (e.g. MassSpec) should not trigger the guard."""
        graph = make_step_graph()
        step_a = PlanStepNode(
            search_name="GenesByGoTerm",
            parameters={"organism": '["Plasmodium falciparum 3D7"]'},
        )
        step_b = PlanStepNode(
            search_name="GenesByMassSpec",
            parameters={"ms_assay": '["merozoite_Plasmodium falciparum 3D7"]'},
        )
        populate_graph(graph, step_a, step_b)
        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                primary_input_step_id=step_a.id,
                secondary_input_step_id=step_b.id,
                operator="INTERSECT",
            ),
            callbacks=make_step_creation_callbacks(),
        )
        assert result.error is None
        assert result.step is not None

    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_intersect_orthologs_output_vs_different_species_rejected(
        self, mock_val: AsyncMock
    ) -> None:
        """Orthologs(Pf→Pb) INTERSECT Pf_expression should fail — Pb IDs vs Pf IDs."""
        graph = make_step_graph()
        pf_kinases = PlanStepNode(
            search_name="GenesByGoTerm",
            parameters={"organism": '["Plasmodium falciparum 3D7"]'},
        )
        ortho_step = PlanStepNode(
            search_name="GenesByOrthologs",
            parameters={"organism": '["Plasmodium berghei ANKA"]'},
            primary_input=pf_kinases,
        )
        pf_expr_step = PlanStepNode(
            search_name="GenesByRNASeqPercentile",
            parameters={"organism": '["Plasmodium falciparum 3D7"]'},
        )
        populate_graph(graph, pf_kinases, ortho_step, pf_expr_step)
        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                primary_input_step_id=ortho_step.id,
                secondary_input_step_id=pf_expr_step.id,
                operator="INTERSECT",
            ),
            callbacks=make_step_creation_callbacks(),
        )
        assert result.error is not None
        assert result.error["code"] == "INVALID_STRATEGY"
        assert "berghei" in str(result.error["message"]).lower()
        assert "falciparum" in str(result.error["message"]).lower()

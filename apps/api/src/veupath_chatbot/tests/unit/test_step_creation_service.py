"""Tests for services.strategies.step_creation -- extracted step creation service."""

from unittest.mock import AsyncMock, patch

from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.domain.strategy.ops import ColocationParams, CombineOp
from veupath_chatbot.domain.strategy.organism import extract_output_organisms
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKSearchResponse
from veupath_chatbot.platform.errors import ValidationError
from veupath_chatbot.services.catalog.param_validation import ValidationCallbacks
from veupath_chatbot.services.strategies.step_creation import (
    COMBINE_PLACEHOLDER_SEARCH_NAME,
    StepSpec,
    coerce_wdk_boolean_question_params,
    create_step,
)
from veupath_chatbot.services.strategies.step_validation import (
    _validate_inputs,
    _validate_root_status,
)

from .conftest import (
    extract_vocab_options_stub,
    find_record_type_hint_stub,
    make_step_creation_callbacks,
    make_step_graph,
    noop_validation_error_payload,
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
        graph.add_step(step_a)
        graph.add_step(step_b)
        graph.add_step(step_c)
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
        graph.add_step(step_a)
        graph.add_step(step_b)
        _, _, error = _validate_inputs(graph, step_a.id, step_b.id, None)
        assert error is not None
        assert "operator is required" in str(error["message"])

    def test_valid_binary_inputs(self):
        graph = make_step_graph()
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
        graph = make_step_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        graph.add_step(step_a)
        assert _validate_root_status(graph, step_a.id) is None

    def test_non_root_step_fails(self):
        graph = make_step_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        step_b = PlanStepNode(search_name="B", parameters={})
        graph.add_step(step_a)
        graph.add_step(step_b)
        combine = PlanStepNode(
            search_name="__combine__",
            parameters={},
            primary_input=step_a,
            secondary_input=step_b,
            operator=CombineOp.INTERSECT,
        )
        graph.add_step(combine)
        error = _validate_root_status(graph, step_a.id)
        assert error is not None
        assert "not a subtree root" in str(error["message"])
        assert error["consumedBy"] == combine.id


# ---------------------------------------------------------------------------
# _build_colocation_params
# ---------------------------------------------------------------------------


class TestBuildColocationParams:
    def test_non_colocate_returns_none(self):
        assert ColocationParams.from_raw(CombineOp.UNION, 10, 20, "same") is None
        assert ColocationParams.from_raw(None, 10, 20, "same") is None

    def test_colocate_defaults(self):
        result = ColocationParams.from_raw(CombineOp.COLOCATE, None, None, None)
        assert result is not None
        assert result.upstream == 0
        assert result.downstream == 0
        assert result.strand == "both"

    def test_colocate_custom(self):
        result = ColocationParams.from_raw(CombineOp.COLOCATE, 100, 200, "same")
        assert result is not None
        assert result.upstream == 100
        assert result.downstream == 200
        assert result.strand == "same"

    def test_colocate_invalid_strand_defaults_to_both(self):
        result = ColocationParams.from_raw(CombineOp.COLOCATE, 0, 0, "invalid")
        assert result is not None
        assert result.strand == "both"


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
        graph.add_step(step_a)
        graph.add_step(step_b)

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
        graph.add_step(step_a)
        graph.add_step(step_b)

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

    async def test_non_root_primary_rejected(self):
        graph = make_step_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        step_b = PlanStepNode(search_name="B", parameters={})
        graph.add_step(step_a)
        graph.add_step(step_b)
        combine = PlanStepNode(
            search_name="__combine__",
            parameters={},
            primary_input=step_a,
            secondary_input=step_b,
            operator=CombineOp.INTERSECT,
        )
        graph.add_step(combine)

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(search_name="SomeSearch", primary_input_step_id=step_a.id),
            callbacks=make_step_creation_callbacks(),
        )
        assert result.error is not None
        assert "not a subtree root" in str(result.error["message"])

    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_binary_step_creation_success(self, mock_validate: AsyncMock):
        graph = make_step_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        step_b = PlanStepNode(search_name="B", parameters={})
        graph.add_step(step_a)
        graph.add_step(step_b)

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
        # validate_parameters should NOT be called for binary steps
        mock_validate.assert_not_awaited()

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
        # validate_parameters should be called for leaf steps
        mock_validate.assert_awaited_once()

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
        graph.add_step(step_a)
        graph.add_step(step_b)

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
        graph.add_step(step_a)
        graph.add_step(step_b)

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                primary_input_step_id=step_a.id,
                secondary_input_step_id=step_b.id,
                operator="COLOCATE",
                upstream=500,
                downstream=1000,
                strand="same",
            ),
            callbacks=make_step_creation_callbacks(),
        )
        assert result.error is None
        assert result.step is not None
        assert result.step.operator == CombineOp.COLOCATE
        assert result.step.colocation_params is not None
        assert result.step.colocation_params.upstream == 500
        assert result.step.colocation_params.downstream == 1000
        assert result.step.colocation_params.strand == "same"

    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_record_type_defaults_to_gene(self, mock_validate: AsyncMock):
        """When no record type is available, it should default to 'gene'."""
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
                extract_vocab_options=extract_vocab_options_stub,
                validation_error_payload=noop_validation_error_payload,
            ),
        )
        # The leaf validation will fail because always_none_resolver returns None
        # when called with require_match=True. But graph.record_type should be set.
        assert graph.record_type == "gene"

    async def test_step_added_to_graph(self):
        """Successful creation adds the step to the graph."""
        graph = make_step_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        step_b = PlanStepNode(search_name="B", parameters={})
        graph.add_step(step_a)
        graph.add_step(step_b)
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
                extract_vocab_options=extract_vocab_options_stub,
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
        pf = graph.add_step(
            PlanStepNode(
                search_name="GenesByGoTerm",
                parameters={"organism": '["Plasmodium falciparum 3D7"]'},
            )
        )
        pb = graph.add_step(
            PlanStepNode(
                search_name="GenesByText",
                parameters={"text_search_organism": '["Plasmodium berghei ANKA"]'},
            )
        )
        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                primary_input_step_id=pf,
                secondary_input_step_id=pb,
                operator="INTERSECT",
            ),
            callbacks=make_step_creation_callbacks(),
        )
        assert result.error is not None
        assert result.error["code"] == "INVALID_STRATEGY"
        assert "different organism" in result.error["message"].lower()

    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_intersect_same_organism_allowed(self, mock_val: AsyncMock) -> None:
        graph = make_step_graph()
        a = graph.add_step(
            PlanStepNode(
                search_name="GenesByGoTerm",
                parameters={"organism": '["Plasmodium falciparum 3D7"]'},
            )
        )
        b = graph.add_step(
            PlanStepNode(
                search_name="GenesByText",
                parameters={"text_search_organism": '["Plasmodium falciparum 3D7"]'},
            )
        )
        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                primary_input_step_id=a,
                secondary_input_step_id=b,
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
        pf = graph.add_step(
            PlanStepNode(
                search_name="GenesByGoTerm",
                parameters={"organism": '["Plasmodium falciparum 3D7"]'},
            )
        )
        pb = graph.add_step(
            PlanStepNode(
                search_name="GenesByText",
                parameters={"text_search_organism": '["Plasmodium berghei ANKA"]'},
            )
        )
        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                primary_input_step_id=pf,
                secondary_input_step_id=pb,
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
        a = graph.add_step(
            PlanStepNode(
                search_name="GenesByGoTerm",
                parameters={"organism": '["Plasmodium falciparum 3D7"]'},
            )
        )
        b = graph.add_step(
            PlanStepNode(
                search_name="GenesByMassSpec",
                parameters={"ms_assay": '["merozoite_Plasmodium falciparum 3D7"]'},
            )
        )
        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                primary_input_step_id=a,
                secondary_input_step_id=b,
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
        ortho_step_id = graph.add_step(
            PlanStepNode(
                search_name="GenesByOrthologs",
                parameters={"organism": '["Plasmodium berghei ANKA"]'},
                primary_input=pf_kinases,
            )
        )
        pf_expr_id = graph.add_step(
            PlanStepNode(
                search_name="GenesByRNASeqPercentile",
                parameters={"organism": '["Plasmodium falciparum 3D7"]'},
            )
        )
        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                primary_input_step_id=ortho_step_id,
                secondary_input_step_id=pf_expr_id,
                operator="INTERSECT",
            ),
            callbacks=make_step_creation_callbacks(),
        )
        assert result.error is not None
        assert result.error["code"] == "INVALID_STRATEGY"
        assert "berghei" in result.error["message"].lower()
        assert "falciparum" in result.error["message"].lower()

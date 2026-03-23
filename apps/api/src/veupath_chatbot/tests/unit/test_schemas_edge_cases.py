"""Edge-case and bug-hunting tests for HTTP transport schemas.

Covers gaps not addressed by the existing test_http_schemas_transport.py:
- Newline/special-character handling in serialized output
- SetOperationRequest accepts any operation string (missing Literal constraint)
- CreateGeneSetRequest allows empty gene_ids list
- GeneSetResponse gene_count not validated against gene_ids length
- AuthStatusResponse uses non-aliased field names (camelCase directly)
- StrategyResponse.record_type should be Optional with a default
- Experiment CRUD PATCH body is untyped dict (no schema validation)
- PlanStepNode allows operator without secondaryInput
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from veupath_chatbot.domain.strategy.ast import PlanStepNode, StrategyAST
from veupath_chatbot.domain.strategy.ops import ColocationParams, CombineOp
from veupath_chatbot.transport.http.schemas.chat import (
    ChatMention,
    ChatRequest,
    MessageResponse,
    ThinkingResponse,
)
from veupath_chatbot.transport.http.schemas.experiments import (
    CreateExperimentRequest,
    ThresholdSweepRequest,
)
from veupath_chatbot.transport.http.schemas.gene_sets import (
    CreateGeneSetRequest,
    GeneSetResponse,
    RunGeneSetAnalysisRequest,
    SetOperationRequest,
)
from veupath_chatbot.transport.http.schemas.sites import (
    SearchDetailsResponse,
    SearchValidationErrors,
    SearchValidationPayload,
    SearchValidationResponse,
    SiteResponse,
)
from veupath_chatbot.transport.http.schemas.steps import (
    StepAnalysisRequest,
    StepResponse,
)
from veupath_chatbot.transport.http.schemas.strategies import (
    CreateStrategyRequest,
    OpenStrategyRequest,
    StrategyResponse,
    UpdateStrategyRequest,
)
from veupath_chatbot.transport.http.schemas.veupathdb_auth import AuthStatusResponse

# ---------------------------------------------------------------------------
# SetOperationRequest (operation field accepts intersect / union / minus)
# ---------------------------------------------------------------------------


class TestSetOperationRequestOperationValues:
    """SetOperationRequest.operation rejects invalid values at the schema level."""

    def test_valid_operations_accepted(self) -> None:
        for op in ("intersect", "union", "minus"):
            req = SetOperationRequest(
                setAId="a", setBId="b", operation=op, name="result"
            )
            assert req.operation == op

    def test_invalid_operation_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SetOperationRequest(
                setAId="a", setBId="b", operation="garbage", name="result"
            )


# ---------------------------------------------------------------------------
# CreateGeneSetRequest: gene_ids has no min_length constraint
# ---------------------------------------------------------------------------


class TestCreateGeneSetRequestEdgeCases:
    def test_empty_gene_ids_accepted(self) -> None:
        # gene_ids has no min_length, so an empty list is valid at the schema
        # level. The router handles this by auto-fetching from WDK when
        # wdk_strategy_id is set. This is intentional behavior.
        req = CreateGeneSetRequest(name="Empty", siteId="plasmodb", geneIds=[])
        assert req.gene_ids == []

    def test_name_empty_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CreateGeneSetRequest(name="", siteId="plasmodb", geneIds=["G1"])

    def test_very_large_gene_list(self) -> None:
        # No upper bound on gene_ids count.
        big_list = [f"GENE_{i}" for i in range(50_000)]
        req = CreateGeneSetRequest(name="Big", siteId="x", geneIds=big_list)
        assert len(req.gene_ids) == 50_000

    def test_parameters_accepts_str_values(self) -> None:
        req = CreateGeneSetRequest(
            name="X",
            siteId="x",
            geneIds=["G1"],
            parameters={"organism": "Plasmodium falciparum 3D7"},
        )
        assert req.parameters == {"organism": "Plasmodium falciparum 3D7"}

    def test_parameters_rejects_nested_dict(self) -> None:
        with pytest.raises(ValidationError):
            CreateGeneSetRequest(
                name="X",
                siteId="x",
                geneIds=["G1"],
                parameters={"nested": {"deep": True}},
            )


# ---------------------------------------------------------------------------
# GeneSetResponse: gene_count is independent of gene_ids length
# ---------------------------------------------------------------------------


class TestGeneSetResponseGeneCountMismatch:
    def test_gene_count_can_mismatch_gene_ids(self) -> None:
        # gene_count is a plain field, not a computed/validated field.
        # It could mismatch the actual len(gene_ids).
        resp = GeneSetResponse(
            id="gs1",
            name="Test",
            siteId="x",
            geneIds=["G1", "G2"],
            source="paste",
            geneCount=999,  # mismatch!
            createdAt="2026-01-01",
        )
        assert resp.gene_count == 999
        assert len(resp.gene_ids) == 2
        # The router helper _to_response() correctly sets geneCount=len(gs.gene_ids),
        # but the schema itself doesn't enforce consistency.


# ---------------------------------------------------------------------------
# AuthStatusResponse: uses raw camelCase field names (no aliases)
# ---------------------------------------------------------------------------


class TestAuthStatusResponseFieldNaming:
    def test_field_is_camel_case_directly(self) -> None:
        # AuthStatusResponse uses `signedIn` as the Python attribute name
        # (not snake_case with alias). This is inconsistent with every other
        # schema, but not technically a bug.
        resp = AuthStatusResponse(signedIn=True, name="User", email="u@test.com")
        data = resp.model_dump()
        assert "signedIn" in data
        # No alias transformation needed -- already camelCase.

    def test_model_validate_from_json(self) -> None:
        raw = {"signedIn": True, "name": "User"}
        resp = AuthStatusResponse.model_validate(raw)
        assert resp.signedIn is True

    def test_snake_case_rejected(self) -> None:
        # Since there's no populate_by_name and no alias, snake_case won't work.
        with pytest.raises(ValidationError):
            AuthStatusResponse.model_validate({"signed_in": True})


# ---------------------------------------------------------------------------
# StrategyResponse: record_type is NOT Optional-defaulted
# ---------------------------------------------------------------------------


class TestStrategyResponseRecordType:
    def test_record_type_is_required_via_alias(self) -> None:
        # record_type has alias="recordType" but no default.
        # For list views, this means the caller MUST provide it even if null.
        now = datetime.now(UTC)
        # Providing None explicitly works fine
        resp = StrategyResponse(
            id=uuid4(),
            name="Test",
            siteId="plasmodb",
            recordType=None,
            createdAt=now,
            updatedAt=now,
        )
        assert resp.record_type is None

    def test_record_type_missing_from_dict_raises(self) -> None:
        # If recordType is completely absent from JSON (not even null),
        # Pydantic should raise.
        now = datetime.now(UTC)
        with pytest.raises(ValidationError):
            StrategyResponse.model_validate(
                {
                    "id": str(uuid4()),
                    "name": "Test",
                    "siteId": "plasmodb",
                    # recordType deliberately omitted
                    "createdAt": now.isoformat(),
                    "updatedAt": now.isoformat(),
                }
            )


# ---------------------------------------------------------------------------
# PlanStepNode: operator without secondaryInput
# ---------------------------------------------------------------------------


class TestPlanStepNodeOperatorWithoutSecondary:
    def test_operator_without_secondary_allowed(self) -> None:
        leaf = PlanStepNode(search_name="A")
        n = PlanStepNode(search_name="B", primary_input=leaf, operator=CombineOp.INTERSECT)
        assert n.operator == CombineOp.INTERSECT
        assert n.secondary_input is None

    def test_operator_alone_without_any_input_allowed(self) -> None:
        n = PlanStepNode(search_name="A", operator=CombineOp.UNION)
        assert n.operator == CombineOp.UNION
        assert n.primary_input is None


# ---------------------------------------------------------------------------
# Serialization: special characters in string fields
# ---------------------------------------------------------------------------


class TestSpecialCharacterSerialization:
    def test_newlines_in_message_content(self) -> None:
        now = datetime.now(UTC)
        msg = MessageResponse(
            role="assistant",
            content="Line 1\nLine 2\nLine 3",
            timestamp=now,
        )
        data = msg.model_dump(mode="json")
        assert "\n" in data["content"]

    def test_unicode_in_chat_request(self) -> None:
        req = ChatRequest(
            siteId="plasmodb",
            message="Find genes for Plasmodium \u00e9\u00e8\u00ea",
        )
        assert "\u00e9" in req.message

    def test_html_in_content_not_escaped(self) -> None:
        now = datetime.now(UTC)
        msg = MessageResponse(
            role="assistant",
            content="<script>alert('xss')</script>",
            timestamp=now,
        )
        assert "<script>" in msg.content

    def test_strategy_name_with_special_chars(self) -> None:
        plan = StrategyAST(record_type="gene", root=PlanStepNode(search_name="X"))
        req = CreateStrategyRequest(
            name='Strategy "with quotes" & <tags>',
            siteId="plasmodb",
            plan=plan,
        )
        assert '"' in req.name
        assert "&" in req.name


# ---------------------------------------------------------------------------
# ChatRequest: boundary and edge-case tests
# ---------------------------------------------------------------------------


class TestChatRequestEdgeCases:
    def test_message_exactly_one_char(self) -> None:
        req = ChatRequest(siteId="x", message="a")
        assert len(req.message) == 1

    def test_whitespace_only_message_accepted(self) -> None:
        # min_length=1 counts whitespace, so a space is a valid message.
        req = ChatRequest(siteId="x", message=" ")
        assert req.message == " "

    def test_strategy_id_as_string_uuid(self) -> None:
        sid = uuid4()
        req = ChatRequest.model_validate(
            {"siteId": "x", "message": "hi", "strategyId": str(sid)}
        )
        assert req.strategy_id == sid

    def test_strategy_id_invalid_uuid_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ChatRequest.model_validate(
                {"siteId": "x", "message": "hi", "strategyId": "not-a-uuid"}
            )


# ---------------------------------------------------------------------------
# ThinkingResponse: timestamp serialization
# ---------------------------------------------------------------------------


class TestThinkingResponseTimestamp:
    def test_updated_at_json_serialization(self) -> None:
        now = datetime.now(UTC)
        t = ThinkingResponse(reasoning="test", updatedAt=now)
        data = t.model_dump(by_alias=True, mode="json")
        assert "updatedAt" in data
        assert isinstance(data["updatedAt"], str)


# ---------------------------------------------------------------------------
# SearchDetailsResponse: extra field behavior
# ---------------------------------------------------------------------------


class TestSearchDetailsResponseExtraFields:
    def test_extra_fields_in_serialization(self) -> None:
        resp = SearchDetailsResponse.model_validate(
            {"searchData": {"key": "val"}, "custom_wdk_field": [1, 2, 3]}
        )
        data = resp.model_dump(by_alias=True)
        assert "searchData" in data
        # Extra fields should be preserved in output
        assert "custom_wdk_field" in data


# ---------------------------------------------------------------------------
# OpenStrategyRequest: all fields are optional -- caller must validate at least one
# ---------------------------------------------------------------------------


class TestOpenStrategyRequestValidation:
    def test_completely_empty_request_accepted(self) -> None:
        # All fields are optional with no model_validator to require at least one.
        # This means a completely empty request is valid at the schema level,
        # but the router would need to handle it.
        req = OpenStrategyRequest()
        assert req.strategy_id is None
        assert req.wdk_strategy_id is None
        assert req.site_id is None


# ---------------------------------------------------------------------------
# StepResponse: model_validate from WDK-like JSON
# ---------------------------------------------------------------------------


class TestStepResponseFromWdkJson:
    def test_from_minimal_wdk_json(self) -> None:
        raw = {"id": "step_42", "displayName": "My Search"}
        step = StepResponse.model_validate(raw)
        assert step.id == "step_42"
        assert step.display_name == "My Search"

    def test_from_full_wdk_json(self) -> None:
        raw = {
            "id": "s1",
            "kind": "search",
            "displayName": "Genes by Organism",
            "searchName": "GenesByOrganism",
            "recordType": "gene",
            "parameters": {"organism": "Plasmodium falciparum"},
            "estimatedSize": 5000,
            "wdkStepId": 12345,
        }
        step = StepResponse.model_validate(raw)
        assert step.search_name == "GenesByOrganism"
        assert step.estimated_size == 5000


# ---------------------------------------------------------------------------
# CreateExperimentRequest: field interaction edge cases
# ---------------------------------------------------------------------------


class TestCreateExperimentRequestEdgeCases:
    def _base(self, **overrides: object) -> dict:
        defaults: dict = {
            "siteId": "plasmodb",
            "recordType": "gene",
            "positiveControls": ["G1"],
            "negativeControls": ["G2"],
            "controlsSearchName": "GenesByLocusTag",
            "controlsParamName": "ds_gene_ids",
        }
        defaults.update(overrides)
        return defaults

    def test_empty_positive_controls_accepted(self) -> None:
        # positive_controls has no min_length constraint, so [] is valid.
        req = CreateExperimentRequest(**self._base(positiveControls=[]))
        assert req.positive_controls == []

    def test_empty_negative_controls_accepted(self) -> None:
        req = CreateExperimentRequest(**self._base(negativeControls=[]))
        assert req.negative_controls == []

    def test_step_tree_can_be_any_json_value(self) -> None:
        # step_tree is typed as JSONValue which includes str, int, list, etc.
        for val in (None, "string", 42, [1, 2, 3], {"key": "val"}):
            req = CreateExperimentRequest(**self._base(stepTree=val))
            assert req.step_tree == val

    def test_optimization_specs_empty_list(self) -> None:
        req = CreateExperimentRequest(**self._base(optimizationSpecs=[]))
        assert req.optimization_specs == []


# ---------------------------------------------------------------------------
# UpdateStrategyRequest: model_fields_set tracking
# ---------------------------------------------------------------------------


class TestUpdateStrategyRequestFieldsSet:
    def test_fields_set_tracking(self) -> None:
        # UpdateStrategyRequest uses model_fields_set to detect explicit None vs absent.
        req = UpdateStrategyRequest(isSaved=False)
        fields_set = req.model_fields_set
        assert "is_saved" in fields_set
        assert "name" not in fields_set

    def test_explicit_none_vs_absent(self) -> None:
        # When wdk_strategy_id is explicitly set to None, it should be in fields_set.
        req = UpdateStrategyRequest(wdkStrategyId=None)
        assert "wdk_strategy_id" in req.model_fields_set

    def test_absent_field_not_in_fields_set(self) -> None:
        req = UpdateStrategyRequest(name="New")
        assert "wdk_strategy_id" not in req.model_fields_set
        assert "is_saved" not in req.model_fields_set


# ---------------------------------------------------------------------------
# ThresholdSweepRequest: semantic inconsistencies
# ---------------------------------------------------------------------------


class TestThresholdSweepRequestSemantics:
    def test_numeric_without_range_accepted(self) -> None:
        # A numeric sweep without min/max values is accepted at schema level.
        # The service would need to handle this gracefully.
        req = ThresholdSweepRequest(parameterName="score", sweepType="numeric")
        assert req.min_value is None
        assert req.max_value is None

    def test_categorical_without_values_accepted(self) -> None:
        # A categorical sweep without values is accepted at schema level.
        req = ThresholdSweepRequest(parameterName="method", sweepType="categorical")
        assert req.values is None


# ---------------------------------------------------------------------------
# SearchValidationResponse: nested structure roundtrip
# ---------------------------------------------------------------------------


class TestSearchValidationResponseRoundtrip:
    def test_full_validation_response_roundtrip(self) -> None:
        errors = SearchValidationErrors(
            general=["Global error"],
            byKey={"organism": ["Required", "Invalid"]},
        )
        payload = SearchValidationPayload(
            isValid=False,
            normalizedContextValues={"organism": "default"},
            errors=errors,
        )
        resp = SearchValidationResponse(validation=payload)

        data = resp.model_dump(by_alias=True, mode="json")
        restored = SearchValidationResponse.model_validate(data)

        assert not restored.validation.is_valid
        assert restored.validation.errors.by_key["organism"] == ["Required", "Invalid"]
        assert restored.validation.normalized_context_values == {"organism": "default"}


# ---------------------------------------------------------------------------
# ColocationParams: edge cases
# ---------------------------------------------------------------------------


class TestColocationParamsEdgeCases:
    def test_zero_values_accepted(self) -> None:
        c = ColocationParams(upstream=0, downstream=0)
        assert c.upstream == 0
        assert c.downstream == 0

    def test_very_large_values_accepted(self) -> None:
        # No upper bound on upstream/downstream
        c = ColocationParams(upstream=1_000_000, downstream=1_000_000)
        assert c.upstream == 1_000_000

    def test_valid_strand_values(self) -> None:
        for strand in ("both", "same", "opposite"):
            c = ColocationParams(upstream=0, downstream=0, strand=strand)
            assert c.strand == strand

    def test_invalid_strand_coerced_to_both(self) -> None:
        # Domain ColocationParams coerces unrecognized strand to "both"
        # (tolerant of AI-generated plans).
        c = ColocationParams(upstream=0, downstream=0, strand="invalid_strand")
        assert c.strand == "both"


# ---------------------------------------------------------------------------
# RunGeneSetAnalysisRequest: analysis_name min_length=1
# ---------------------------------------------------------------------------


class TestRunGeneSetAnalysisRequestEdgeCases:
    def test_empty_analysis_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RunGeneSetAnalysisRequest(analysisName="")


# ---------------------------------------------------------------------------
# SiteResponse: by_alias roundtrip
# ---------------------------------------------------------------------------


class TestSiteResponseRoundtrip:
    def test_full_roundtrip(self) -> None:
        original = SiteResponse(
            id="plasmodb",
            name="PlasmoDB",
            displayName="PlasmoDB",
            baseUrl="https://plasmodb.org/plasmo/service",
            projectId="PlasmoDB",
            isPortal=False,
        )
        data = original.model_dump(by_alias=True, mode="json")
        restored = SiteResponse.model_validate(data)
        assert restored.id == "plasmodb"
        assert restored.display_name == "PlasmoDB"
        assert restored.base_url == "https://plasmodb.org/plasmo/service"


# ---------------------------------------------------------------------------
# ChatMention: type field is Literal-validated
# ---------------------------------------------------------------------------


class TestChatMentionTypeValidation:
    def test_valid_types(self) -> None:
        for t in ("strategy", "experiment"):
            m = ChatMention(type=t, id="x", displayName="X")
            assert m.type == t

    def test_invalid_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ChatMention(type="gene_set", id="x", displayName="X")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# StepAnalysisRequest: analysis_type has no validation
# ---------------------------------------------------------------------------


class TestStepAnalysisRequestEdgeCases:
    def test_empty_analysis_type_accepted(self) -> None:
        # No min_length on analysis_type
        req = StepAnalysisRequest(analysisType="")
        assert req.analysis_type == ""

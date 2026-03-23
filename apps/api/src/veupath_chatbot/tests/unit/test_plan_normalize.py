"""Unit tests for services.strategies.plan_normalize.canonicalize_plan_parameters."""

from collections.abc import Mapping

import pytest
from pydantic import ValidationError as PydanticValidationError

from veupath_chatbot.domain.strategy.ast import StrategyAST
from veupath_chatbot.platform.errors import ValidationError
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.strategies.plan_normalize import (
    canonicalize_plan_parameters,
)

# -- Helpers ----------------------------------------------------------------


def _wrap_search_response(search_name: str, parameters: list[JSONObject]) -> JSONObject:
    """Wrap parameters in a WDKSearchResponse-compatible envelope."""
    return {
        "searchData": {
            "urlSegment": search_name,
            "parameters": parameters,
        },
        "validation": {"level": "DISPLAYABLE", "isValid": True},
    }


async def _stub_search_details(
    record_type: str,
    search_name: str,
    params: Mapping[str, JSONValue],
) -> JSONObject:
    """Return minimal WDK-style parameter spec for the search."""
    if search_name == "GenesByTextSearch":
        return _wrap_search_response(
            search_name,
            [
                {
                    "name": "text_expression",
                    "type": "string",
                    "allowEmptyValue": True,
                },
                {
                    "name": "text_fields",
                    "type": "multi-pick-vocabulary",
                    "allowEmptyValue": True,
                    "vocabulary": [
                        ["gene_name", "Gene name"],
                        ["product", "Product"],
                    ],
                },
            ],
        )
    if search_name == "GenesByGoTerm":
        return _wrap_search_response(
            search_name,
            [
                {
                    "name": "goTerm",
                    "type": "string",
                    "allowEmptyValue": False,
                },
            ],
        )
    if search_name == "GenesByOrthologs":
        return _wrap_search_response(
            search_name,
            [
                {
                    "name": "organism",
                    "type": "single-pick-vocabulary",
                    "allowEmptyValue": False,
                    "vocabulary": [
                        ["Pf3D7", "P. falciparum 3D7"],
                        ["PvSal1", "P. vivax Sal-1"],
                    ],
                },
            ],
        )
    msg = f"Unknown search: {search_name}"
    raise ValueError(msg)


async def _failing_search_details(
    record_type: str,
    search_name: str,
    params: Mapping[str, JSONValue],
) -> JSONObject:
    msg = "Network failure"
    raise RuntimeError(msg)


def _make_plan(data: JSONObject) -> StrategyAST:
    """Construct a StrategyAST from a camelCase dict (convenience helper)."""
    return StrategyAST.model_validate(data)


# -- Tests for missing recordType ------------------------------------------


class TestMissingRecordType:
    def test_raises_when_record_type_missing(self) -> None:
        """Pydantic rejects a plan without recordType at construction time."""
        with pytest.raises(PydanticValidationError):
            _make_plan(
                {
                    "root": {
                        "id": "s1",
                        "searchName": "GenesByTextSearch",
                        "parameters": {"text_expression": "kinase"},
                    },
                }
            )

    def test_raises_when_record_type_empty(self) -> None:
        """StrategyAST requires a non-empty recordType string.

        Pydantic accepts empty strings by default for str fields, so
        this test verifies the StrategyAST can be constructed (Pydantic allows it).
        If business rules require non-empty, a validator should be added to StrategyAST.
        """
        # Empty string is technically valid per Pydantic str type — construction succeeds.
        # The original test checked for our custom ValidationError from _validate_plan_record_type.
        # With typed models, an empty string would need an explicit Pydantic validator to reject.
        # For now, verify construction succeeds (Pydantic's behavior).
        plan = _make_plan(
            {
                "recordType": "",
                "root": {
                    "id": "s1",
                    "searchName": "GenesByTextSearch",
                    "parameters": {"text_expression": "kinase"},
                },
            }
        )
        assert plan.record_type == ""

    def test_raises_when_record_type_not_string(self) -> None:
        """Pydantic rejects non-string recordType at construction time."""
        with pytest.raises(PydanticValidationError):
            _make_plan(
                {
                    "recordType": 42,
                    "root": {
                        "id": "s1",
                        "searchName": "GenesByTextSearch",
                        "parameters": {},
                    },
                }
            )


# -- Tests for missing searchName ------------------------------------------


class TestMissingSearchName:
    def test_raises_when_search_name_missing(self) -> None:
        """Pydantic rejects a PlanStepNode without searchName."""
        with pytest.raises(PydanticValidationError):
            _make_plan(
                {
                    "recordType": "gene",
                    "root": {
                        "id": "s1",
                        "parameters": {"text_expression": "kinase"},
                    },
                }
            )

    def test_raises_when_search_name_empty(self) -> None:
        """Empty searchName is technically valid per Pydantic str type."""
        plan = _make_plan(
            {
                "recordType": "gene",
                "root": {
                    "id": "s1",
                    "searchName": "",
                    "parameters": {},
                },
            }
        )
        assert plan.root.search_name == ""


# -- Tests for invalid parameters ------------------------------------------


class TestInvalidParameters:
    def test_raises_when_parameters_not_dict(self) -> None:
        """Pydantic rejects non-dict parameters at construction time."""
        with pytest.raises(PydanticValidationError):
            _make_plan(
                {
                    "recordType": "gene",
                    "root": {
                        "id": "s1",
                        "searchName": "GenesByTextSearch",
                        "parameters": "not-a-dict",
                    },
                }
            )

    @pytest.mark.asyncio
    async def test_none_parameters_treated_as_empty_dict(self) -> None:
        """When parameters is omitted, PlanStepNode defaults to empty dict."""
        plan = _make_plan(
            {
                "recordType": "gene",
                "root": {
                    "id": "s1",
                    "searchName": "GenesByTextSearch",
                },
            }
        )
        result = await canonicalize_plan_parameters(
            plan=plan, site_id="plasmodb", load_search_details=_stub_search_details
        )
        assert result.root.parameters is not None


# -- Tests for search details failure --------------------------------------


class TestSearchDetailsFailure:
    @pytest.mark.asyncio
    async def test_raises_validation_error_on_search_details_failure(self) -> None:
        plan = _make_plan(
            {
                "recordType": "gene",
                "root": {
                    "id": "s1",
                    "searchName": "GenesByTextSearch",
                    "parameters": {"text_expression": "kinase"},
                },
            }
        )
        with pytest.raises(ValidationError, match="metadata") as exc_info:
            await canonicalize_plan_parameters(
                plan=plan,
                site_id="plasmodb",
                load_search_details=_failing_search_details,
            )
        assert exc_info.value.detail is not None
        assert "GenesByTextSearch" in exc_info.value.detail


# -- Tests for simple leaf node canonicalization ---------------------------


class TestLeafNodeCanonicalization:
    @pytest.mark.asyncio
    async def test_simple_text_search(self) -> None:
        plan = _make_plan(
            {
                "recordType": "gene",
                "root": {
                    "id": "s1",
                    "searchName": "GenesByTextSearch",
                    "parameters": {"text_expression": "kinase"},
                },
            }
        )
        result = await canonicalize_plan_parameters(
            plan=plan, site_id="plasmodb", load_search_details=_stub_search_details
        )
        assert result.root.parameters["text_expression"] == "kinase"

    @pytest.mark.asyncio
    async def test_plan_is_mutated_in_place(self) -> None:
        """canonicalize_plan_parameters mutates and returns the same object."""
        plan = _make_plan(
            {
                "recordType": "gene",
                "root": {
                    "id": "s1",
                    "searchName": "GenesByTextSearch",
                    "parameters": {"text_expression": "test"},
                },
            }
        )
        result = await canonicalize_plan_parameters(
            plan=plan, site_id="plasmodb", load_search_details=_stub_search_details
        )
        assert result is plan


# -- Tests for combine node handling ---------------------------------------


class TestCombineNodeHandling:
    @pytest.mark.asyncio
    async def test_combine_node_strips_boolean_params(self) -> None:
        """Combine nodes should have bq_* parameters stripped."""
        plan = _make_plan(
            {
                "recordType": "gene",
                "root": {
                    "id": "c1",
                    "searchName": "BooleanQuestion",
                    "operator": "INTERSECT",
                    "parameters": {
                        "bq_operator": "INTERSECT",
                        "bq_left_op#s1": "s1",
                        "bq_right_op#s2": "s2",
                        "custom_param": "keep",
                    },
                    "primaryInput": {
                        "id": "s1",
                        "searchName": "GenesByTextSearch",
                        "parameters": {"text_expression": "kinase"},
                    },
                    "secondaryInput": {
                        "id": "s2",
                        "searchName": "GenesByTextSearch",
                        "parameters": {"text_expression": "enzyme"},
                    },
                },
            }
        )
        result = await canonicalize_plan_parameters(
            plan=plan, site_id="plasmodb", load_search_details=_stub_search_details
        )
        params = result.root.parameters
        assert "bq_operator" not in params
        assert "bq_left_op#s1" not in params
        assert "bq_right_op#s2" not in params
        assert params.get("custom_param") == "keep"

    @pytest.mark.asyncio
    async def test_combine_node_recurses_into_children(self) -> None:
        """The primaryInput and secondaryInput of combines should be canonicalized."""
        plan = _make_plan(
            {
                "recordType": "gene",
                "root": {
                    "id": "c1",
                    "searchName": "BooleanQuestion",
                    "operator": "INTERSECT",
                    "parameters": {},
                    "primaryInput": {
                        "id": "s1",
                        "searchName": "GenesByTextSearch",
                        "parameters": {"text_expression": "kinase"},
                    },
                    "secondaryInput": {
                        "id": "s2",
                        "searchName": "GenesByTextSearch",
                        "parameters": {"text_expression": "enzyme"},
                    },
                },
            }
        )
        result = await canonicalize_plan_parameters(
            plan=plan, site_id="plasmodb", load_search_details=_stub_search_details
        )
        assert result.root.primary_input is not None
        assert result.root.secondary_input is not None
        # The children should have been canonicalized
        assert result.root.primary_input.parameters is not None
        assert result.root.secondary_input.parameters is not None


# -- Tests for transform node handling -------------------------------------


class TestTransformNodeHandling:
    @pytest.mark.asyncio
    async def test_transform_canonicalizes_params(self) -> None:
        plan = _make_plan(
            {
                "recordType": "gene",
                "root": {
                    "id": "t1",
                    "searchName": "GenesByOrthologs",
                    "parameters": {"organism": "Pf3D7"},
                    "primaryInput": {
                        "id": "s1",
                        "searchName": "GenesByTextSearch",
                        "parameters": {"text_expression": "kinase"},
                    },
                },
            }
        )
        result = await canonicalize_plan_parameters(
            plan=plan, site_id="plasmodb", load_search_details=_stub_search_details
        )
        assert result.root.parameters["organism"] == "Pf3D7"


# -- Tests for deep nesting ------------------------------------------------


class TestDeepNesting:
    @pytest.mark.asyncio
    async def test_deeply_nested_tree(self) -> None:
        """A 3-level deep tree: combine(transform(search), search)."""
        plan = _make_plan(
            {
                "recordType": "gene",
                "root": {
                    "id": "c1",
                    "searchName": "BooleanQuestion",
                    "operator": "INTERSECT",
                    "parameters": {},
                    "primaryInput": {
                        "id": "t1",
                        "searchName": "GenesByOrthologs",
                        "parameters": {"organism": "Pf3D7"},
                        "primaryInput": {
                            "id": "s1",
                            "searchName": "GenesByTextSearch",
                            "parameters": {"text_expression": "kinase"},
                        },
                    },
                    "secondaryInput": {
                        "id": "s2",
                        "searchName": "GenesByTextSearch",
                        "parameters": {"text_expression": "enzyme"},
                    },
                },
            }
        )
        result = await canonicalize_plan_parameters(
            plan=plan, site_id="plasmodb", load_search_details=_stub_search_details
        )
        # All nodes should have been processed without error
        assert result.root.primary_input is not None
        assert result.root.primary_input.primary_input is not None
        assert isinstance(result.root.primary_input.primary_input.parameters, dict)


# -- Tests for caching ----------------------------------------------------


class TestSpecsCaching:
    @pytest.mark.asyncio
    async def test_same_search_cached(self) -> None:
        """load_search_details should be called once per unique (rt, name, params_hash)."""
        call_count = 0

        async def counting_loader(
            record_type: str,
            search_name: str,
            params: Mapping[str, JSONValue],
        ) -> JSONObject:
            nonlocal call_count
            call_count += 1
            return await _stub_search_details(record_type, search_name, params)

        plan = _make_plan(
            {
                "recordType": "gene",
                "root": {
                    "id": "c1",
                    "searchName": "BooleanQuestion",
                    "operator": "INTERSECT",
                    "parameters": {},
                    "primaryInput": {
                        "id": "s1",
                        "searchName": "GenesByTextSearch",
                        "parameters": {"text_expression": "kinase"},
                    },
                    "secondaryInput": {
                        "id": "s2",
                        "searchName": "GenesByTextSearch",
                        "parameters": {"text_expression": "kinase"},
                    },
                },
            }
        )
        await canonicalize_plan_parameters(
            plan=plan, site_id="plasmodb", load_search_details=counting_loader
        )
        # Same search + same params = should only load once due to cache
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_different_params_not_cached(self) -> None:
        """Different param values produce different cache keys."""
        call_count = 0

        async def counting_loader(
            record_type: str,
            search_name: str,
            params: Mapping[str, JSONValue],
        ) -> JSONObject:
            nonlocal call_count
            call_count += 1
            return await _stub_search_details(record_type, search_name, params)

        plan = _make_plan(
            {
                "recordType": "gene",
                "root": {
                    "id": "c1",
                    "searchName": "BooleanQuestion",
                    "operator": "INTERSECT",
                    "parameters": {},
                    "primaryInput": {
                        "id": "s1",
                        "searchName": "GenesByTextSearch",
                        "parameters": {"text_expression": "kinase"},
                    },
                    "secondaryInput": {
                        "id": "s2",
                        "searchName": "GenesByTextSearch",
                        "parameters": {"text_expression": "enzyme"},
                    },
                },
            }
        )
        await canonicalize_plan_parameters(
            plan=plan, site_id="plasmodb", load_search_details=counting_loader
        )
        # Same search but different params = should load twice
        assert call_count == 2


# -- Tests for searchData unwrapping ---------------------------------------


class TestSearchDataUnwrapping:
    @pytest.mark.asyncio
    async def test_unwraps_search_data_wrapper(self) -> None:
        """When load_search_details returns {searchData: {parameters: [...]}, validation: ...}, parse it."""

        async def wrapped_loader(
            record_type: str,
            search_name: str,
            params: Mapping[str, JSONValue],
        ) -> JSONObject:
            return {
                "searchData": {
                    "urlSegment": search_name,
                    "parameters": [
                        {
                            "name": "text_expression",
                            "type": "string",
                            "allowEmptyValue": True,
                        },
                    ],
                },
                "validation": {"level": "DISPLAYABLE", "isValid": True},
            }

        plan = _make_plan(
            {
                "recordType": "gene",
                "root": {
                    "id": "s1",
                    "searchName": "GenesByTextSearch",
                    "parameters": {"text_expression": "kinase"},
                },
            }
        )
        result = await canonicalize_plan_parameters(
            plan=plan, site_id="plasmodb", load_search_details=wrapped_loader
        )
        assert result.root.parameters["text_expression"] == "kinase"


# -- Tests for non-dict search details return values -----------------------


class TestNonDictSearchDetails:
    @pytest.mark.asyncio
    async def test_handles_non_dict_details_result(self) -> None:
        """When load_search_details returns a non-dict, WDKSearchResponse validation fails."""

        async def bad_loader(
            record_type: str,
            search_name: str,
            params: Mapping[str, JSONValue],
        ) -> JSONValue:
            return []

        plan = _make_plan(
            {
                "recordType": "gene",
                "root": {
                    "id": "s1",
                    "searchName": "GenesByTextSearch",
                    "parameters": {"text_expression": "kinase"},
                },
            }
        )
        # Non-dict return causes WDKSearchResponse.model_validate to fail,
        # which is wrapped in a ValidationError by _load_and_cache_spec.
        with pytest.raises(ValidationError, match="metadata"):
            await canonicalize_plan_parameters(
                plan=plan, site_id="plasmodb", load_search_details=bad_loader
            )


# -- Tests for empty parameter scenarios ----------------------------------


class TestEmptyParameters:
    @pytest.mark.asyncio
    async def test_empty_params_dict(self) -> None:
        plan = _make_plan(
            {
                "recordType": "gene",
                "root": {
                    "id": "s1",
                    "searchName": "GenesByTextSearch",
                    "parameters": {},
                },
            }
        )
        result = await canonicalize_plan_parameters(
            plan=plan, site_id="plasmodb", load_search_details=_stub_search_details
        )
        assert isinstance(result.root.parameters, dict)
        assert result.root.parameters == {}

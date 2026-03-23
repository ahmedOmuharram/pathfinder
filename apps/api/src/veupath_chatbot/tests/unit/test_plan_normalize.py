"""Unit tests for services.strategies.plan_normalize.canonicalize_plan_parameters."""

from collections.abc import Mapping

import pytest

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


# -- Tests for missing recordType ------------------------------------------


class TestMissingRecordType:
    @pytest.mark.asyncio
    async def test_raises_when_record_type_missing(self) -> None:
        plan: JSONObject = {
            "root": {
                "id": "s1",
                "searchName": "GenesByTextSearch",
                "parameters": {"text_expression": "kinase"},
            },
        }
        with pytest.raises(ValidationError, match="Invalid plan"):
            await canonicalize_plan_parameters(
                plan=plan, site_id="plasmodb", load_search_details=_stub_search_details
            )

    @pytest.mark.asyncio
    async def test_raises_when_record_type_empty(self) -> None:
        plan: JSONObject = {
            "recordType": "",
            "root": {
                "id": "s1",
                "searchName": "GenesByTextSearch",
                "parameters": {"text_expression": "kinase"},
            },
        }
        with pytest.raises(ValidationError, match="Invalid plan") as exc_info:
            await canonicalize_plan_parameters(
                plan=plan, site_id="plasmodb", load_search_details=_stub_search_details
            )
        assert exc_info.value.detail is not None
        assert "recordType" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_raises_when_record_type_not_string(self) -> None:
        plan: JSONObject = {
            "recordType": 42,
            "root": {
                "id": "s1",
                "searchName": "GenesByTextSearch",
                "parameters": {},
            },
        }
        with pytest.raises(ValidationError, match="Invalid plan") as exc_info:
            await canonicalize_plan_parameters(
                plan=plan, site_id="plasmodb", load_search_details=_stub_search_details
            )
        assert exc_info.value.detail is not None
        assert "recordType" in exc_info.value.detail


# -- Tests for missing root ------------------------------------------------


class TestMissingRoot:
    @pytest.mark.asyncio
    async def test_returns_plan_when_root_not_dict(self) -> None:
        """When root is not a dict, plan is returned unchanged."""
        plan: JSONObject = {"recordType": "gene", "root": "not-a-dict"}
        result = await canonicalize_plan_parameters(
            plan=plan, site_id="plasmodb", load_search_details=_stub_search_details
        )
        assert result is plan

    @pytest.mark.asyncio
    async def test_returns_plan_when_root_missing(self) -> None:
        plan: JSONObject = {"recordType": "gene"}
        result = await canonicalize_plan_parameters(
            plan=plan, site_id="plasmodb", load_search_details=_stub_search_details
        )
        assert result is plan


# -- Tests for missing searchName ------------------------------------------


class TestMissingSearchName:
    @pytest.mark.asyncio
    async def test_raises_when_search_name_missing(self) -> None:
        plan: JSONObject = {
            "recordType": "gene",
            "root": {
                "id": "s1",
                "parameters": {"text_expression": "kinase"},
            },
        }
        with pytest.raises(ValidationError, match="Invalid plan") as exc_info:
            await canonicalize_plan_parameters(
                plan=plan, site_id="plasmodb", load_search_details=_stub_search_details
            )
        assert exc_info.value.detail is not None
        assert "searchName" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_raises_when_search_name_empty(self) -> None:
        plan: JSONObject = {
            "recordType": "gene",
            "root": {
                "id": "s1",
                "searchName": "",
                "parameters": {},
            },
        }
        with pytest.raises(ValidationError, match="Invalid plan") as exc_info:
            await canonicalize_plan_parameters(
                plan=plan, site_id="plasmodb", load_search_details=_stub_search_details
            )
        assert exc_info.value.detail is not None
        assert "searchName" in exc_info.value.detail


# -- Tests for invalid parameters ------------------------------------------


class TestInvalidParameters:
    @pytest.mark.asyncio
    async def test_raises_when_parameters_not_dict(self) -> None:
        plan: JSONObject = {
            "recordType": "gene",
            "root": {
                "id": "s1",
                "searchName": "GenesByTextSearch",
                "parameters": "not-a-dict",
            },
        }
        with pytest.raises(ValidationError, match="Invalid plan") as exc_info:
            await canonicalize_plan_parameters(
                plan=plan, site_id="plasmodb", load_search_details=_stub_search_details
            )
        assert exc_info.value.detail is not None
        assert "parameters" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_none_parameters_treated_as_empty_dict(self) -> None:
        """When parameters is None, it should be treated as empty dict."""
        plan: JSONObject = {
            "recordType": "gene",
            "root": {
                "id": "s1",
                "searchName": "GenesByTextSearch",
            },
        }
        result = await canonicalize_plan_parameters(
            plan=plan, site_id="plasmodb", load_search_details=_stub_search_details
        )
        assert isinstance(result["root"], dict)
        root = result["root"]
        assert isinstance(root, dict)
        assert root.get("parameters") is not None


# -- Tests for search details failure --------------------------------------


class TestSearchDetailsFailure:
    @pytest.mark.asyncio
    async def test_raises_validation_error_on_search_details_failure(self) -> None:
        plan: JSONObject = {
            "recordType": "gene",
            "root": {
                "id": "s1",
                "searchName": "GenesByTextSearch",
                "parameters": {"text_expression": "kinase"},
            },
        }
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
        plan: JSONObject = {
            "recordType": "gene",
            "root": {
                "id": "s1",
                "searchName": "GenesByTextSearch",
                "parameters": {"text_expression": "kinase"},
            },
        }
        result = await canonicalize_plan_parameters(
            plan=plan, site_id="plasmodb", load_search_details=_stub_search_details
        )
        root = result["root"]
        assert isinstance(root, dict)
        params = root.get("parameters")
        assert isinstance(params, dict)
        assert params["text_expression"] == "kinase"

    @pytest.mark.asyncio
    async def test_plan_is_mutated_in_place(self) -> None:
        """canonicalize_plan_parameters mutates and returns the same object."""
        plan: JSONObject = {
            "recordType": "gene",
            "root": {
                "id": "s1",
                "searchName": "GenesByTextSearch",
                "parameters": {"text_expression": "test"},
            },
        }
        result = await canonicalize_plan_parameters(
            plan=plan, site_id="plasmodb", load_search_details=_stub_search_details
        )
        assert result is plan


# -- Tests for combine node handling ---------------------------------------


class TestCombineNodeHandling:
    @pytest.mark.asyncio
    async def test_combine_node_strips_boolean_params(self) -> None:
        """Combine nodes should have bq_* parameters stripped."""
        plan: JSONObject = {
            "recordType": "gene",
            "root": {
                "id": "c1",
                "searchName": "BooleanQuestion",
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
        result = await canonicalize_plan_parameters(
            plan=plan, site_id="plasmodb", load_search_details=_stub_search_details
        )
        root = result["root"]
        assert isinstance(root, dict)
        params = root.get("parameters", {})
        assert isinstance(params, dict)
        assert "bq_operator" not in params
        assert "bq_left_op#s1" not in params
        assert "bq_right_op#s2" not in params
        assert params.get("custom_param") == "keep"

    @pytest.mark.asyncio
    async def test_combine_node_recurses_into_children(self) -> None:
        """The primaryInput and secondaryInput of combines should be canonicalized."""
        plan: JSONObject = {
            "recordType": "gene",
            "root": {
                "id": "c1",
                "searchName": "BooleanQuestion",
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
        result = await canonicalize_plan_parameters(
            plan=plan, site_id="plasmodb", load_search_details=_stub_search_details
        )
        root = result["root"]
        assert isinstance(root, dict)
        primary = root.get("primaryInput")
        secondary = root.get("secondaryInput")
        assert isinstance(primary, dict)
        assert isinstance(secondary, dict)
        # The children should have been canonicalized
        assert primary.get("parameters") is not None
        assert secondary.get("parameters") is not None


# -- Tests for transform node handling -------------------------------------


class TestTransformNodeHandling:
    @pytest.mark.asyncio
    async def test_transform_canonicalizes_params(self) -> None:
        plan: JSONObject = {
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
        result = await canonicalize_plan_parameters(
            plan=plan, site_id="plasmodb", load_search_details=_stub_search_details
        )
        root = result["root"]
        assert isinstance(root, dict)
        params = root.get("parameters")
        assert isinstance(params, dict)
        assert params["organism"] == "Pf3D7"


# -- Tests for deep nesting ------------------------------------------------


class TestDeepNesting:
    @pytest.mark.asyncio
    async def test_deeply_nested_tree(self) -> None:
        """A 3-level deep tree: combine(transform(search), search)."""
        plan: JSONObject = {
            "recordType": "gene",
            "root": {
                "id": "c1",
                "searchName": "BooleanQuestion",
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
        result = await canonicalize_plan_parameters(
            plan=plan, site_id="plasmodb", load_search_details=_stub_search_details
        )
        # All nodes should have been processed without error
        root = result["root"]
        assert isinstance(root, dict)
        primary = root.get("primaryInput")
        assert isinstance(primary, dict)
        inner_primary = primary.get("primaryInput")
        assert isinstance(inner_primary, dict)
        assert isinstance(inner_primary.get("parameters"), dict)


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

        plan: JSONObject = {
            "recordType": "gene",
            "root": {
                "id": "c1",
                "searchName": "BooleanQuestion",
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

        plan: JSONObject = {
            "recordType": "gene",
            "root": {
                "id": "c1",
                "searchName": "BooleanQuestion",
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

        plan: JSONObject = {
            "recordType": "gene",
            "root": {
                "id": "s1",
                "searchName": "GenesByTextSearch",
                "parameters": {"text_expression": "kinase"},
            },
        }
        result = await canonicalize_plan_parameters(
            plan=plan, site_id="plasmodb", load_search_details=wrapped_loader
        )
        root = result["root"]
        assert isinstance(root, dict)
        params = root.get("parameters")
        assert isinstance(params, dict)
        assert params["text_expression"] == "kinase"


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

        plan: JSONObject = {
            "recordType": "gene",
            "root": {
                "id": "s1",
                "searchName": "GenesByTextSearch",
                "parameters": {"text_expression": "kinase"},
            },
        }
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
        plan: JSONObject = {
            "recordType": "gene",
            "root": {
                "id": "s1",
                "searchName": "GenesByTextSearch",
                "parameters": {},
            },
        }
        result = await canonicalize_plan_parameters(
            plan=plan, site_id="plasmodb", load_search_details=_stub_search_details
        )
        root = result["root"]
        assert isinstance(root, dict)
        params = root.get("parameters")
        assert isinstance(params, dict)
        assert params == {}

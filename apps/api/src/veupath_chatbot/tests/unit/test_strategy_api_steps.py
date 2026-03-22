"""Unit tests for veupath_chatbot.integrations.veupathdb.strategy_api.steps.

Tests StepsMixin: create_step, create_combined_step, create_transform_step,
create_dataset, and internal helpers (_get_boolean_search_name,
_get_boolean_param_names, _get_answer_param_names).

Verified against live WDK data:
- Gene boolean search is "boolean_question_GeneRecordClasses_GeneRecordClass"
- Boolean param names: bq_left_op_GeneRecordClasses_GeneRecordClass,
  bq_right_op_GeneRecordClasses_GeneRecordClass, bq_operator
- Search details wrapped under "searchData" key
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from veupath_chatbot.integrations.veupathdb.strategy_api.steps import StepsMixin
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKSearch,
    WDKSearchResponse,
)
from veupath_chatbot.platform.errors import DataParsingError, InternalError, WDKError


def _make_mixin(user_id: str = "12345") -> tuple[StepsMixin, MagicMock]:
    """Create StepsMixin with a mock client, pre-initialized session."""
    client = MagicMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    client.get_searches = AsyncMock()
    client.get_search_details = AsyncMock()
    mixin = StepsMixin(client, user_id=user_id)
    mixin._session_initialized = True
    return mixin, client


# ---------------------------------------------------------------------------
# _get_boolean_search_name
# ---------------------------------------------------------------------------


class TestGetBooleanSearchName:
    """Resolves the boolean combine search name for a record type.

    Live WDK: gene -> "boolean_question_GeneRecordClasses_GeneRecordClass"
    """

    async def test_finds_boolean_search(self) -> None:
        mixin, client = _make_mixin()
        client.get_searches.return_value = [
            WDKSearch.model_validate({"urlSegment": "GenesByTaxonGene"}),
            WDKSearch.model_validate({"urlSegment": "boolean_question_GeneRecordClasses_GeneRecordClass"}),
        ]
        name = await mixin._get_boolean_search_name("gene")
        assert name == "boolean_question_GeneRecordClasses_GeneRecordClass"

    async def test_caches_result(self) -> None:
        mixin, client = _make_mixin()
        client.get_searches.return_value = [
            WDKSearch.model_validate({"urlSegment": "boolean_question_GeneRecordClasses_GeneRecordClass"}),
        ]
        await mixin._get_boolean_search_name("gene")
        await mixin._get_boolean_search_name("gene")
        client.get_searches.assert_awaited_once()

    async def test_raises_when_not_found(self) -> None:
        mixin, client = _make_mixin()
        client.get_searches.return_value = [
            WDKSearch.model_validate({"urlSegment": "GenesByTaxonGene"}),
        ]
        with pytest.raises(DataParsingError, match="No boolean combine search"):
            await mixin._get_boolean_search_name("gene")


# ---------------------------------------------------------------------------
# _get_boolean_param_names
# ---------------------------------------------------------------------------


class TestGetBooleanParamNames:
    """Resolves left, right, operator param names for boolean combine.

    Live WDK returns paramNames: [
        "bq_left_op_GeneRecordClasses_GeneRecordClass",
        "bq_right_op_GeneRecordClasses_GeneRecordClass",
        "bq_operator"
    ]
    """

    async def test_resolves_param_names(self) -> None:
        mixin, client = _make_mixin()
        client.get_searches.return_value = [
            WDKSearch.model_validate({"urlSegment": "boolean_question_GeneRecordClasses_GeneRecordClass"}),
        ]
        client.get_search_details.return_value = WDKSearchResponse.model_validate({
            "searchData": {
                "urlSegment": "boolean_question_GeneRecordClasses_GeneRecordClass",
                "paramNames": [
                    "bq_left_op_GeneRecordClasses_GeneRecordClass",
                    "bq_right_op_GeneRecordClasses_GeneRecordClass",
                    "bq_operator",
                ],
            },
            "validation": {"level": "DISPLAYABLE", "isValid": True},
        })
        left, right, op = await mixin._get_boolean_param_names("gene")
        assert left == "bq_left_op_GeneRecordClasses_GeneRecordClass"
        assert right == "bq_right_op_GeneRecordClasses_GeneRecordClass"
        assert op == "bq_operator"

    async def test_raises_when_params_missing(self) -> None:
        mixin, client = _make_mixin()
        client.get_searches.return_value = [
            WDKSearch.model_validate({"urlSegment": "boolean_question_GeneRecordClasses_GeneRecordClass"}),
        ]
        client.get_search_details.return_value = WDKSearchResponse.model_validate({
            "searchData": {
                "urlSegment": "boolean_question_GeneRecordClasses_GeneRecordClass",
                "paramNames": ["bq_operator"],
            },
            "validation": {"level": "DISPLAYABLE", "isValid": True},
        })
        with pytest.raises(DataParsingError, match="Boolean param names not found"):
            await mixin._get_boolean_param_names("gene")

    async def test_raises_when_no_param_names_list(self) -> None:
        """With typed models, empty paramNames means no bq_ params are found."""
        mixin, client = _make_mixin()
        client.get_searches.return_value = [
            WDKSearch.model_validate({"urlSegment": "boolean_question_GeneRecordClasses_GeneRecordClass"}),
        ]
        client.get_search_details.return_value = WDKSearchResponse.model_validate({
            "searchData": {
                "urlSegment": "boolean_question_GeneRecordClasses_GeneRecordClass",
                "paramNames": [],
            },
            "validation": {"level": "DISPLAYABLE", "isValid": True},
        })
        with pytest.raises(DataParsingError, match="Boolean param names not found"):
            await mixin._get_boolean_param_names("gene")


# ---------------------------------------------------------------------------
# _get_answer_param_names
# ---------------------------------------------------------------------------


class TestGetAnswerParamNames:
    """Resolves AnswerParam (input-step) names for transform searches."""

    async def test_finds_input_step_params(self) -> None:
        mixin, client = _make_mixin()
        client.get_search_details.return_value = WDKSearchResponse.model_validate({
            "searchData": {
                "urlSegment": "GenesByRNASeqEvidence",
                "parameters": [
                    {"name": "gene_result", "type": "input-step"},
                    {"name": "threshold", "type": "number"},
                ],
            },
            "validation": {"level": "DISPLAYABLE", "isValid": True},
        })
        names = await mixin._get_answer_param_names(
            "transcript", "GenesByRNASeqEvidence"
        )
        assert names == {"gene_result"}

    async def test_caches_result(self) -> None:
        mixin, client = _make_mixin()
        client.get_search_details.return_value = WDKSearchResponse.model_validate({
            "searchData": {
                "urlSegment": "SomeTransform",
                "parameters": [
                    {"name": "gene_result", "type": "input-step"},
                ],
            },
            "validation": {"level": "DISPLAYABLE", "isValid": True},
        })
        await mixin._get_answer_param_names("transcript", "SomeTransform")
        await mixin._get_answer_param_names("transcript", "SomeTransform")
        client.get_search_details.assert_awaited_once()

    async def test_returns_empty_on_failure(self) -> None:
        """Catches AppError (WDKError, DataParsingError, etc.) gracefully."""
        mixin, client = _make_mixin()
        client.get_search_details.side_effect = WDKError("network failure")
        names = await mixin._get_answer_param_names("gene", "BadSearch")
        assert names == set()


# ---------------------------------------------------------------------------
# create_step
# ---------------------------------------------------------------------------


class TestCreateStep:
    """Step creation sends normalized parameters to WDK."""

    async def test_basic_step_creation(self) -> None:
        mixin, client = _make_mixin()
        client.post.return_value = {"id": 100}

        result = await mixin.create_step(
            record_type="gene",
            search_name="GenesByTaxonGene",
            parameters={"organism": '["Plasmodium falciparum 3D7"]'},
        )

        assert result.id == 100
        call_args = client.post.call_args
        assert "/users/12345/steps" in call_args.args[0]
        payload = call_args.kwargs["json"]
        assert payload["searchName"] == "GenesByTaxonGene"
        assert "parameters" in payload["searchConfig"]

    async def test_step_with_custom_name(self) -> None:
        mixin, client = _make_mixin()
        client.post.return_value = {"id": 100}

        await mixin.create_step(
            record_type="gene",
            search_name="GenesByTaxonGene",
            parameters={},
            custom_name="My Search",
        )

        payload = client.post.call_args.kwargs["json"]
        assert payload["customName"] == "My Search"

    async def test_empty_params_are_kept(self) -> None:
        """Parameters with empty string values are kept (WDK allowEmptyValue)."""
        mixin, client = _make_mixin()
        client.post.return_value = {"id": 100}

        await mixin.create_step(
            record_type="gene",
            search_name="GenesByTaxonGene",
            parameters={"text": "kinase", "empty_field": ""},
        )

        params = client.post.call_args.kwargs["json"]["searchConfig"]["parameters"]
        assert "text" in params
        assert params["empty_field"] == ""


# ---------------------------------------------------------------------------
# create_combined_step
# ---------------------------------------------------------------------------


class TestCreateCombinedStep:
    """Combined (boolean) step creation."""

    async def test_creates_combined_step(self) -> None:
        mixin, client = _make_mixin()
        # Setup boolean search resolution
        client.get_searches.return_value = [
            WDKSearch.model_validate({"urlSegment": "boolean_question_GeneRecordClasses_GeneRecordClass"}),
        ]
        client.get_search_details.return_value = WDKSearchResponse.model_validate({
            "searchData": {
                "urlSegment": "boolean_question_GeneRecordClasses_GeneRecordClass",
                "paramNames": [
                    "bq_left_op_GeneRecordClasses_GeneRecordClass",
                    "bq_right_op_GeneRecordClasses_GeneRecordClass",
                    "bq_operator",
                ],
            },
            "validation": {"level": "DISPLAYABLE", "isValid": True},
        })
        client.post.return_value = {"id": 300}

        result = await mixin.create_combined_step(
            primary_step_id=100,
            secondary_step_id=200,
            boolean_operator="INTERSECT",
            record_type="gene",
        )

        assert result.id == 300
        payload = client.post.call_args.kwargs["json"]
        assert (
            payload["searchName"]
            == "boolean_question_GeneRecordClasses_GeneRecordClass"
        )
        params = payload["searchConfig"]["parameters"]
        # Left and right are empty strings (wired via stepTree)
        assert params["bq_left_op_GeneRecordClasses_GeneRecordClass"] == ""
        assert params["bq_right_op_GeneRecordClasses_GeneRecordClass"] == ""
        assert params["bq_operator"] == "INTERSECT"

    async def test_combined_step_with_custom_name(self) -> None:
        mixin, client = _make_mixin()
        client.get_searches.return_value = [
            WDKSearch.model_validate({"urlSegment": "boolean_question_GeneRecordClasses_GeneRecordClass"}),
        ]
        client.get_search_details.return_value = WDKSearchResponse.model_validate({
            "searchData": {
                "urlSegment": "boolean_question_GeneRecordClasses_GeneRecordClass",
                "paramNames": [
                    "bq_left_op_GeneRecordClasses_GeneRecordClass",
                    "bq_right_op_GeneRecordClasses_GeneRecordClass",
                    "bq_operator",
                ],
            },
            "validation": {"level": "DISPLAYABLE", "isValid": True},
        })
        client.post.return_value = {"id": 300}

        await mixin.create_combined_step(
            primary_step_id=100,
            secondary_step_id=200,
            boolean_operator="UNION",
            record_type="gene",
            custom_name="Union Step",
        )
        payload = client.post.call_args.kwargs["json"]
        assert payload["customName"] == "Union Step"


# ---------------------------------------------------------------------------
# create_transform_step
# ---------------------------------------------------------------------------


class TestCreateTransformStep:
    """Transform step creation with AnswerParam handling."""

    async def test_clears_answer_params_to_empty_string(self) -> None:
        """WDK requires input-step params to be '' on step creation."""
        mixin, client = _make_mixin()
        client.get_search_details.return_value = WDKSearchResponse.model_validate({
            "searchData": {
                "urlSegment": "GenesByRNASeqEvidence",
                "parameters": [
                    {"name": "gene_result", "type": "input-step"},
                    {"name": "threshold", "type": "number"},
                ],
            },
            "validation": {"level": "DISPLAYABLE", "isValid": True},
        })
        client.post.return_value = {"id": 400}

        await mixin.create_transform_step(
            input_step_id=100,
            transform_name="GenesByRNASeqEvidence",
            parameters={
                "gene_result": "should_be_cleared",
                "threshold": "10",
            },
            record_type="transcript",
        )

        payload = client.post.call_args.kwargs["json"]
        params = payload["searchConfig"]["parameters"]
        # AnswerParam forced to ""
        assert params["gene_result"] == ""
        # Regular param preserved
        assert params["threshold"] == "10"

    async def test_adds_missing_answer_params(self) -> None:
        """Even if caller doesn't include the AnswerParam, it should be added as ''."""
        mixin, client = _make_mixin()
        client.get_search_details.return_value = WDKSearchResponse.model_validate({
            "searchData": {
                "urlSegment": "SomeTransform",
                "parameters": [
                    {"name": "gene_result", "type": "input-step"},
                ],
            },
            "validation": {"level": "DISPLAYABLE", "isValid": True},
        })
        client.post.return_value = {"id": 400}

        await mixin.create_transform_step(
            input_step_id=100,
            transform_name="SomeTransform",
            parameters={"threshold": "10"},
            record_type="transcript",
        )

        params = client.post.call_args.kwargs["json"]["searchConfig"]["parameters"]
        assert params["gene_result"] == ""


# ---------------------------------------------------------------------------
# create_dataset
# ---------------------------------------------------------------------------


class TestCreateDataset:
    """Dataset upload for DatasetParam parameters."""

    async def test_creates_dataset_and_returns_id(self) -> None:
        mixin, client = _make_mixin()
        client.post.return_value = {"id": 999}

        ds_id = await mixin.create_dataset(["PF3D7_0100100", "PF3D7_0200200"])

        assert ds_id == 999
        payload = client.post.call_args.kwargs["json"]
        assert payload["sourceType"] == "idList"
        assert payload["sourceContent"]["ids"] == ["PF3D7_0100100", "PF3D7_0200200"]

    async def test_raises_on_missing_id_in_response(self) -> None:
        mixin, client = _make_mixin()
        client.post.return_value = {"status": "created"}

        with pytest.raises(InternalError, match="Dataset creation failed"):
            await mixin.create_dataset(["PF3D7_0100100"])

    async def test_raises_on_non_int_id(self) -> None:
        mixin, client = _make_mixin()
        client.post.return_value = {"id": "not_an_int"}

        with pytest.raises(InternalError, match="Dataset creation failed"):
            await mixin.create_dataset(["PF3D7_0100100"])

    async def test_raises_on_non_dict_response(self) -> None:
        mixin, client = _make_mixin()
        client.post.return_value = []

        with pytest.raises(InternalError, match="Dataset creation failed"):
            await mixin.create_dataset(["PF3D7_0100100"])

"""Unit tests for veupath_chatbot.integrations.veupathdb.strategy_api.steps.

Tests StepsMixin: create_step, create_combined_step, create_transform_step,
and internal helpers (_get_boolean_search_name, _get_boolean_param_names,
_get_answer_param_names).

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
    NewStepSpec,
    WDKSearch,
    WDKSearchConfig,
    WDKSearchResponse,
)
from veupath_chatbot.platform.errors import DataParsingError, WDKError


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
            WDKSearch.model_validate(
                {"urlSegment": "boolean_question_GeneRecordClasses_GeneRecordClass"}
            ),
        ]
        name = await mixin._get_boolean_search_name("gene")
        assert name == "boolean_question_GeneRecordClasses_GeneRecordClass"

    async def test_caches_result(self) -> None:
        mixin, client = _make_mixin()
        client.get_searches.return_value = [
            WDKSearch.model_validate(
                {"urlSegment": "boolean_question_GeneRecordClasses_GeneRecordClass"}
            ),
        ]
        name1 = await mixin._get_boolean_search_name("gene")
        name2 = await mixin._get_boolean_search_name("gene")
        assert name1 == name2

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
            WDKSearch.model_validate(
                {"urlSegment": "boolean_question_GeneRecordClasses_GeneRecordClass"}
            ),
        ]
        client.get_search_details.return_value = WDKSearchResponse.model_validate(
            {
                "searchData": {
                    "urlSegment": "boolean_question_GeneRecordClasses_GeneRecordClass",
                    "paramNames": [
                        "bq_left_op_GeneRecordClasses_GeneRecordClass",
                        "bq_right_op_GeneRecordClasses_GeneRecordClass",
                        "bq_operator",
                    ],
                },
                "validation": {"level": "DISPLAYABLE", "isValid": True},
            }
        )
        left, right, op = await mixin._get_boolean_param_names("gene")
        assert left == "bq_left_op_GeneRecordClasses_GeneRecordClass"
        assert right == "bq_right_op_GeneRecordClasses_GeneRecordClass"
        assert op == "bq_operator"

    async def test_raises_when_params_missing(self) -> None:
        mixin, client = _make_mixin()
        client.get_searches.return_value = [
            WDKSearch.model_validate(
                {"urlSegment": "boolean_question_GeneRecordClasses_GeneRecordClass"}
            ),
        ]
        client.get_search_details.return_value = WDKSearchResponse.model_validate(
            {
                "searchData": {
                    "urlSegment": "boolean_question_GeneRecordClasses_GeneRecordClass",
                    "paramNames": ["bq_operator"],
                },
                "validation": {"level": "DISPLAYABLE", "isValid": True},
            }
        )
        with pytest.raises(DataParsingError, match="Boolean param names not found"):
            await mixin._get_boolean_param_names("gene")

    async def test_raises_when_no_param_names_list(self) -> None:
        """With typed models, empty paramNames means no bq_ params are found."""
        mixin, client = _make_mixin()
        client.get_searches.return_value = [
            WDKSearch.model_validate(
                {"urlSegment": "boolean_question_GeneRecordClasses_GeneRecordClass"}
            ),
        ]
        client.get_search_details.return_value = WDKSearchResponse.model_validate(
            {
                "searchData": {
                    "urlSegment": "boolean_question_GeneRecordClasses_GeneRecordClass",
                    "paramNames": [],
                },
                "validation": {"level": "DISPLAYABLE", "isValid": True},
            }
        )
        with pytest.raises(DataParsingError, match="Boolean param names not found"):
            await mixin._get_boolean_param_names("gene")


# ---------------------------------------------------------------------------
# _get_answer_param_names
# ---------------------------------------------------------------------------


class TestGetAnswerParamNames:
    """Resolves AnswerParam (input-step) names for transform searches."""

    async def test_finds_input_step_params(self) -> None:
        mixin, client = _make_mixin()
        client.get_search_details.return_value = WDKSearchResponse.model_validate(
            {
                "searchData": {
                    "urlSegment": "GenesByRNASeqEvidence",
                    "parameters": [
                        {"name": "gene_result", "type": "input-step"},
                        {"name": "threshold", "type": "number"},
                    ],
                },
                "validation": {"level": "DISPLAYABLE", "isValid": True},
            }
        )
        names = await mixin._get_answer_param_names(
            "transcript", "GenesByRNASeqEvidence"
        )
        assert names == {"gene_result"}

    async def test_caches_result(self) -> None:
        mixin, client = _make_mixin()
        client.get_search_details.return_value = WDKSearchResponse.model_validate(
            {
                "searchData": {
                    "urlSegment": "SomeTransform",
                    "parameters": [
                        {"name": "gene_result", "type": "input-step"},
                    ],
                },
                "validation": {"level": "DISPLAYABLE", "isValid": True},
            }
        )
        names1 = await mixin._get_answer_param_names("transcript", "SomeTransform")
        names2 = await mixin._get_answer_param_names("transcript", "SomeTransform")
        assert names1 == names2

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
            NewStepSpec(
                search_name="GenesByTaxonGene",
                search_config=WDKSearchConfig(
                    parameters={"organism": '["Plasmodium falciparum 3D7"]'},
                ),
            ),
            record_type="gene",
        )

        assert result.id == 100



# ---------------------------------------------------------------------------
# create_combined_step
# ---------------------------------------------------------------------------


class TestCreateCombinedStep:
    """Combined (boolean) step creation."""

    async def test_creates_combined_step(self) -> None:
        mixin, client = _make_mixin()
        # Setup boolean search resolution
        client.get_searches.return_value = [
            WDKSearch.model_validate(
                {"urlSegment": "boolean_question_GeneRecordClasses_GeneRecordClass"}
            ),
        ]
        client.get_search_details.return_value = WDKSearchResponse.model_validate(
            {
                "searchData": {
                    "urlSegment": "boolean_question_GeneRecordClasses_GeneRecordClass",
                    "paramNames": [
                        "bq_left_op_GeneRecordClasses_GeneRecordClass",
                        "bq_right_op_GeneRecordClasses_GeneRecordClass",
                        "bq_operator",
                    ],
                },
                "validation": {"level": "DISPLAYABLE", "isValid": True},
            }
        )
        client.post.return_value = {"id": 300}

        result = await mixin.create_combined_step(
            primary_step_id=100,
            secondary_step_id=200,
            boolean_operator="INTERSECT",
            record_type="gene",
        )

        assert result.id == 300



# ---------------------------------------------------------------------------
# create_transform_step
# ---------------------------------------------------------------------------




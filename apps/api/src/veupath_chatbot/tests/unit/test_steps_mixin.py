"""Tests for StepsMixin typed return values.

Verifies that StepsMixin methods return typed WDK models instead of raw dicts:
- find_step → WDKStep
- create_step → WDKIdentifier
- create_combined_step → WDKIdentifier
- create_transform_step → WDKIdentifier
"""

from unittest.mock import AsyncMock

from veupath_chatbot.integrations.veupathdb.strategy_api.steps import StepsMixin
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    NewStepSpec,
    WDKIdentifier,
    WDKSearchConfig,
    WDKStep,
)


def _make_mixin() -> StepsMixin:
    """Build a StepsMixin with a mocked client and minimal base state."""
    mixin = StepsMixin.__new__(StepsMixin)
    mixin.client = AsyncMock()
    mixin._resolved_user_id = "12345"
    mixin._initial_user_id = "12345"
    mixin._session_initialized = True
    mixin._boolean_search_cache = {}
    mixin._answer_param_cache = {}
    return mixin


class TestFindStep:
    """find_step should call GET /users/{uid}/steps/{id} and return WDKStep."""

    async def test_returns_wdk_step(self) -> None:
        mixin = _make_mixin()
        mixin.client.get = AsyncMock(
            return_value={
                "id": 42,
                "searchName": "GenesByTaxon",
                "searchConfig": {"parameters": {}},
            }
        )

        result = await mixin.find_step(42)

        assert isinstance(result, WDKStep)
        assert result.id == 42
        assert result.search_name == "GenesByTaxon"
        mixin.client.get.assert_awaited_once_with("/users/12345/steps/42")

    async def test_uses_explicit_user_id(self) -> None:
        mixin = _make_mixin()
        mixin.client.get = AsyncMock(
            return_value={
                "id": 42,
                "searchName": "GenesByTaxon",
                "searchConfig": {"parameters": {}},
            }
        )

        await mixin.find_step(42, user_id="99999")

        mixin.client.get.assert_awaited_once_with("/users/99999/steps/42")


class TestCreateStepReturnsWDKIdentifier:
    """create_step should return WDKIdentifier instead of JSONObject."""

    async def test_returns_wdk_identifier(self) -> None:
        mixin = _make_mixin()
        mixin.client.post = AsyncMock(return_value={"id": 100})

        result = await mixin.create_step(
            NewStepSpec(
                search_name="GenesByTaxon",
                search_config=WDKSearchConfig(
                    parameters={"organism": "Plasmodium falciparum"},
                ),
            ),
            record_type="transcript",
        )

        assert isinstance(result, WDKIdentifier)
        assert result.id == 100

    async def test_id_accessible_as_attribute(self) -> None:
        mixin = _make_mixin()
        mixin.client.post = AsyncMock(return_value={"id": 200})

        result = await mixin.create_step(
            NewStepSpec(
                search_name="GenesByTaxon",
                search_config=WDKSearchConfig(parameters={}),
            ),
            record_type="transcript",
        )

        # Must be attribute access, not dict .get("id")
        assert result.id == 200


class TestCreateCombinedStepReturnsWDKIdentifier:
    """create_combined_step should return WDKIdentifier."""

    async def test_returns_wdk_identifier(self) -> None:
        mixin = _make_mixin()
        mixin.client.post = AsyncMock(return_value={"id": 300})
        mixin.client.get_searches = AsyncMock(
            return_value=[
                AsyncMock(url_segment="boolean_question_gene"),
            ]
        )
        mixin.client.get_search_details = AsyncMock(
            return_value=AsyncMock(
                search_data=AsyncMock(
                    param_names=[
                        "bq_left_op__genes",
                        "bq_right_op__genes",
                        "bq_operator__genes",
                    ],
                ),
            )
        )

        result = await mixin.create_combined_step(
            primary_step_id=100,
            secondary_step_id=101,
            boolean_operator="INTERSECT",
            record_type="gene",
        )

        assert isinstance(result, WDKIdentifier)
        assert result.id == 300


class TestCreateTransformStepReturnsWDKIdentifier:
    """create_transform_step should return WDKIdentifier."""

    async def test_returns_wdk_identifier(self) -> None:
        mixin = _make_mixin()
        mixin.client.post = AsyncMock(return_value={"id": 400})
        mixin.client.get_search_details = AsyncMock(
            return_value=AsyncMock(
                search_data=AsyncMock(parameters=[]),
            )
        )

        result = await mixin.create_transform_step(
            NewStepSpec(
                search_name="GenesByOrthology",
                search_config=WDKSearchConfig(
                    parameters={"taxon": "Plasmodium"},
                ),
            ),
            input_step_id=100,
            record_type="transcript",
        )

        assert isinstance(result, WDKIdentifier)
        assert result.id == 400

"""Integration tests for WDK step/dataset payload construction.

Uses respx to mock WDK HTTP and verify the exact payloads sent for:
- create_step: searchName + searchConfig with normalized params
- create_combined_step: boolean_question search with bq_* params
- create_transform_step: AnswerParams forced to ""
- create_dataset: sourceType=idList payload (via DatasetsMixin)

WDK contracts validated:
- Step payload shape: {searchName, searchConfig: {parameters, wdkWeight?}, customName?}
- Combined step: bq_left_op="", bq_right_op="", bq_operator=<op>
- Transform step: input-step params forced to "" (wiring via stepTree)
- Dataset creation: {sourceType: "idList", sourceContent: {ids: [...]}}
"""

import json
from unittest.mock import AsyncMock

import pytest
import respx

from veupath_chatbot.integrations.veupathdb.client import VEuPathDBClient
from veupath_chatbot.integrations.veupathdb.strategy_api.base import StrategyAPIBase
from veupath_chatbot.integrations.veupathdb.strategy_api.datasets import DatasetsMixin
from veupath_chatbot.integrations.veupathdb.strategy_api.steps import StepsMixin
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKDatasetConfigIdList,
    WDKDatasetIdListContent,
    WDKSearch,
    WDKSearchResponse,
    WDKValidation,
)


class _TestableSteps(StepsMixin, DatasetsMixin, StrategyAPIBase):
    """Combine StepsMixin and DatasetsMixin with StrategyAPIBase for testing."""


BASE = "https://plasmodb.org/plasmo/service"


def _empty_search_response() -> WDKSearchResponse:
    """Minimal WDKSearchResponse for mocking search details."""
    return WDKSearchResponse(
        search_data=WDKSearch(
            url_segment="mock",
            full_name="Mock",
            display_name="Mock",
            parameters=None,
            groups=[],
        ),
        validation=WDKValidation(),
    )


@pytest.fixture
def api() -> _TestableSteps:
    client = VEuPathDBClient(base_url=BASE, timeout=5.0)
    inst = _TestableSteps(client=client, user_id="12345")
    # Patch tree expansion to no-op (returns params unchanged).
    # This test focuses on payload shape, not tree expansion.
    inst._expand_tree_params_to_leaves = AsyncMock(
        side_effect=lambda rt, sn, params: params
    )
    return inst


# ── create_step payload ───────────────────────────────────────────


class TestCreateStepPayload:
    """Verifies the exact JSON sent to POST /users/{id}/steps.

    Mocks client.post to capture the outbound payload instead of using
    respx, since tree expansion is already patched to no-op.
    """

    @pytest.mark.asyncio
    async def test_basic_search_step_payload(self, api: _TestableSteps) -> None:
        """Step payload must have searchName + searchConfig.parameters."""
        api.client.post = AsyncMock(return_value={"id": 100})
        await api.create_step(
            record_type="transcript",
            search_name="GenesByTaxon",
            parameters={"organism": '["Plasmodium falciparum 3D7"]'},
        )
        api.client.post.assert_awaited_once()
        call_args = api.client.post.call_args
        path = call_args[0][0] if call_args[0] else call_args[1].get("path")
        payload = call_args[1].get("json") or call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("json")

        assert path == "/users/12345/steps"
        assert payload["searchName"] == "GenesByTaxon"
        assert "searchConfig" in payload
        assert "parameters" in payload["searchConfig"]
        # Organism value should be preserved as JSON string
        assert payload["searchConfig"]["parameters"]["organism"] == (
            '["Plasmodium falciparum 3D7"]'
        )

    @pytest.mark.asyncio
    async def test_custom_name_included(self, api: _TestableSteps) -> None:
        api.client.post = AsyncMock(return_value={"id": 100})
        await api.create_step(
            record_type="transcript",
            search_name="GenesByTaxon",
            parameters={"organism": '["pfal"]'},
            custom_name="My Step",
        )
        payload = api.client.post.call_args[1]["json"]
        assert payload["customName"] == "My Step"

    @pytest.mark.asyncio
    async def test_wdk_weight_included(self, api: _TestableSteps) -> None:
        api.client.post = AsyncMock(return_value={"id": 100})
        await api.create_step(
            record_type="transcript",
            search_name="GenesByTaxon",
            parameters={},
            wdk_weight=50,
        )
        payload = api.client.post.call_args[1]["json"]
        assert payload["searchConfig"]["wdkWeight"] == 50

    @pytest.mark.asyncio
    async def test_none_params_omitted(self, api: _TestableSteps) -> None:
        """Parameters with None value should be omitted from WDK payload."""
        api.client.post = AsyncMock(return_value={"id": 100})
        await api.create_step(
            record_type="transcript",
            search_name="GenesByTaxon",
            parameters={"organism": '["pfal"]', "removed": None},
        )
        payload = api.client.post.call_args[1]["json"]
        assert "removed" not in payload["searchConfig"]["parameters"]


# ── create_combined_step payload ──────────────────────────────────


class TestCreateCombinedStepPayload:
    """Verifies combined step's boolean params match WDK contract.

    WDK contract: bq_left_op and bq_right_op MUST be "" (empty string).
    Input wiring happens via stepTree, not parameters.
    """

    @pytest.mark.asyncio
    async def test_boolean_params_are_empty_strings(
        self, api: _TestableSteps
    ) -> None:
        """Verify bq_left_op and bq_right_op are empty strings.

        WDK wires combine step inputs via stepTree, NOT via parameters.
        The bq parameters must be "" at creation time.
        """
        bq_search = "boolean_question_TranscriptRecordClasses_TranscriptRecordClass"
        left_key = "bq_left_op__TranscriptRecordClasses.TranscriptRecordClass"
        right_key = "bq_right_op__TranscriptRecordClasses.TranscriptRecordClass"
        op_key = "bq_operator__TranscriptRecordClasses.TranscriptRecordClass"

        # Mock get_searches to return the boolean question search
        bq_search_obj = WDKSearch(
            url_segment=bq_search,
            full_name="InternalQuestions.BooleanQuestion",
            display_name="Boolean",
            groups=[],
        )
        api.client.get_searches = AsyncMock(return_value=[bq_search_obj])

        # Mock get_search_details to return param names
        bq_details = WDKSearchResponse(
            search_data=WDKSearch(
                url_segment=bq_search,
                full_name="InternalQuestions.BooleanQuestion",
                display_name="Boolean",
                param_names=[left_key, right_key, op_key],
                parameters=None,
                groups=[],
            ),
            validation=WDKValidation(),
        )
        api.client.get_search_details = AsyncMock(return_value=bq_details)
        api.client.post = AsyncMock(return_value={"id": 300})

        await api.create_combined_step(
            primary_step_id=100,
            secondary_step_id=200,
            boolean_operator="INTERSECT",
            record_type="transcript",
        )

        payload = api.client.post.call_args[1]["json"]
        params = payload["searchConfig"]["parameters"]

        # Left and right MUST be empty strings (WDK wires via stepTree)
        assert params[left_key] == ""
        assert params[right_key] == ""
        assert params[op_key] == "INTERSECT"


# ── create_dataset payload ────────────────────────────────────────


class TestCreateDatasetPayload:
    """Verifies dataset upload matches WDK's expected payload."""

    @pytest.mark.asyncio
    async def test_dataset_payload_shape(self, api: _TestableSteps) -> None:
        """WDK expects {sourceType: "idList", sourceContent: {ids: [...]}}."""
        gene_ids = ["PF3D7_0100100", "PF3D7_0831900", "PF3D7_1133400"]
        config = WDKDatasetConfigIdList(
            source_type="idList",
            source_content=WDKDatasetIdListContent(ids=gene_ids),
        )
        with respx.mock:
            # Mock user resolution
            respx.get(f"{BASE}/users/current").respond(200, json={"id": 12345})
            route = respx.post(f"{BASE}/users/12345/datasets").respond(
                200, json={"id": 500}
            )
            dataset_id = await api.create_dataset(config)
            assert dataset_id == 500

            body = json.loads(route.calls[0].request.content)
            assert body["sourceType"] == "idList"
            assert body["sourceContent"]["ids"] == gene_ids

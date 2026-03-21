"""HTTP-level integration tests for control_tests module.

Uses ``respx`` to intercept all outbound httpx calls that the WDK client
makes, exercising the full code path from ``_run_intersection_control`` /
``run_positive_negative_controls`` through StrategyAPI -> VEuPathDBClient ->
httpx without any live network access.

Mirrors the scenarios in ``test_live_control_tests.py`` (which requires a
running PlasmoDB instance) but with deterministic, pre-canned responses.
"""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from veupath_chatbot.integrations.veupathdb.client import VEuPathDBClient
from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.platform.errors import WDKError
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.control_tests import (
    IntersectionConfig,
    _run_intersection_control,
    run_positive_negative_controls,
)
from veupath_chatbot.tests.fixtures.wdk_responses import (
    dataset_creation_response,
    search_details_response,
    searches_response,
    standard_report_response,
    step_creation_response,
    strategy_creation_response,
    user_current_response,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BASE = "https://plasmodb.org/plasmo/service"
USER_ID = 12345
SITE_ID = "plasmodb"
RECORD_TYPE = "transcript"

TARGET_SEARCH_NAME = "GenesByRNASeqpfal3D7_Su_seven_stages_rnaSeq_RSRC"
CONTROLS_SEARCH_NAME = "GeneByLocusTag"
CONTROLS_PARAM_NAME = "ds_gene_ids"

TARGET_PARAMETERS: JSONObject = {
    "regulated_dir": "up-regulated",
    "fold_change": "2",
}

POSITIVE_CONTROLS = [
    "PF3D7_1222600",
    "PF3D7_1031000",
    "PF3D7_0209000",
    "PF3D7_1346700",
    "PF3D7_1346800",
]

NEGATIVE_CONTROLS = [
    "PF3D7_1462800",
    "PF3D7_1246200",
    "PF3D7_0422300",
    "PF3D7_0317600",
]

# Step / strategy IDs
TARGET_STEP_ID = 10001
CONTROLS_STEP_ID = 10002
COMBINED_STEP_ID = 10003
STRATEGY_ID = 20001
DATASET_ID = 30001

PATCH_TARGET = "veupath_chatbot.services.control_tests.get_strategy_api"
PATCH_FIND_RT = "veupath_chatbot.services.control_tests.find_record_type_for_search"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_api() -> StrategyAPI:
    """Build a StrategyAPI wired to a real VEuPathDBClient (HTTP mocked)."""
    client = VEuPathDBClient(base_url=BASE, timeout=5.0)
    return StrategyAPI(client)


def _resp(status: int, body: dict | list | None = None) -> httpx.Response:
    """Build an httpx.Response for respx side_effect lists."""
    if body is None:
        return httpx.Response(status)
    return httpx.Response(status, json=body)


def _mock_session(router: respx.Router) -> None:
    """Mock GET /users/current used by _ensure_session."""
    router.get(f"{BASE}/users/current").respond(
        200, json=user_current_response(USER_ID)
    )


def _mock_searches(router: respx.Router) -> None:
    """Mock GET /record-types/{type}/searches for boolean search discovery."""
    router.get(f"{BASE}/record-types/{RECORD_TYPE}/searches").respond(
        200, json=searches_response()
    )


def _mock_search_details(
    router: respx.Router,
    *,
    controls_param_type: str = "input-dataset",
) -> None:
    """Mock search detail endpoints.

    Registers routes for the boolean search details (needed by
    create_combined_step) and the controls search details (needed by
    resolve_controls_param_type).
    """
    boolean_name = "boolean_question_TranscriptRecordClasses_TranscriptRecordClass"
    router.get(f"{BASE}/record-types/{RECORD_TYPE}/searches/{boolean_name}").respond(
        200, json=search_details_response(boolean_name)
    )

    router.get(
        f"{BASE}/record-types/{RECORD_TYPE}/searches/{CONTROLS_SEARCH_NAME}"
    ).respond(
        200,
        json={
            "searchData": {
                "urlSegment": CONTROLS_SEARCH_NAME,
                "fullName": f"GeneQuestions.{CONTROLS_SEARCH_NAME}",
                "displayName": "Gene by Locus Tag",
                "paramNames": [CONTROLS_PARAM_NAME],
                "groups": [],
                "parameters": [
                    {"name": CONTROLS_PARAM_NAME, "type": controls_param_type},
                ],
            },
            "validation": {"level": "DISPLAYABLE", "isValid": True},
        },
    )

    router.get(
        f"{BASE}/record-types/{RECORD_TYPE}/searches/{TARGET_SEARCH_NAME}"
    ).respond(
        200,
        json={
            "searchData": {
                "urlSegment": TARGET_SEARCH_NAME,
                "fullName": f"GeneQuestions.{TARGET_SEARCH_NAME}",
                "displayName": "RNA-Seq",
                "paramNames": ["regulated_dir", "fold_change"],
                "groups": [],
                "parameters": [
                    {"name": "regulated_dir", "type": "single-pick-vocabulary"},
                    {"name": "fold_change", "type": "number"},
                ],
            },
            "validation": {"level": "DISPLAYABLE", "isValid": True},
        },
    )


def _mock_list_strategies(
    router: respx.Router,
    strategies: list[dict] | None = None,
) -> respx.Route:
    """Mock GET /users/{userId}/strategies for cleanup."""
    return router.get(f"{BASE}/users/{USER_ID}/strategies").respond(
        200, json=strategies or []
    )


def _common_config() -> IntersectionConfig:
    """Return a base IntersectionConfig for _run_intersection_control tests."""
    return IntersectionConfig(
        site_id=SITE_ID,
        record_type=RECORD_TYPE,
        target_search_name=TARGET_SEARCH_NAME,
        target_parameters=TARGET_PARAMETERS,
        controls_search_name=CONTROLS_SEARCH_NAME,
        controls_param_name=CONTROLS_PARAM_NAME,
    )


def _setup_full_intersection(
    router: respx.Router,
    *,
    target_count: int = 500,
    combined_count: int = 3,
    combined_gene_ids: list[str] | None = None,
    controls_param_type: str = "input-dataset",
) -> None:
    """Register all routes for a single _run_intersection_control call.

    The standard report endpoint for a given step is called multiple times
    (count then answer). We use side_effect lists to serve them in order.
    """
    _mock_session(router)
    _mock_searches(router)
    _mock_search_details(router, controls_param_type=controls_param_type)

    # Step creation: target, controls, combined
    router.post(f"{BASE}/users/{USER_ID}/steps").mock(
        side_effect=[
            _resp(200, step_creation_response(TARGET_STEP_ID)),
            _resp(200, step_creation_response(CONTROLS_STEP_ID)),
            _resp(200, step_creation_response(COMBINED_STEP_ID)),
        ]
    )

    if controls_param_type == "input-dataset":
        router.post(f"{BASE}/users/{USER_ID}/datasets").respond(
            200, json=dataset_creation_response(DATASET_ID)
        )

    router.post(f"{BASE}/users/{USER_ID}/strategies").respond(
        200, json=strategy_creation_response(STRATEGY_ID)
    )

    ids = combined_gene_ids or []

    # Report calls: target count, combined count, combined answer
    router.post(url__regex=rf".*/users/{USER_ID}/steps/\d+/reports/standard").mock(
        side_effect=[
            _resp(200, standard_report_response([], target_count)),
            _resp(200, standard_report_response([], combined_count)),
            _resp(200, standard_report_response(ids, combined_count)),
        ]
    )

    router.delete(f"{BASE}/users/{USER_ID}/strategies/{STRATEGY_ID}").respond(204)


# ===================================================================
# 1. Single intersection control -- happy path
# ===================================================================
class TestSingleIntersectionControl:
    """Exercises _run_intersection_control through the real HTTP client stack."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_positive_controls_returns_correct_structure(self) -> None:
        """Target step created, intersection count extracted, cleanup called."""
        hit_ids = POSITIVE_CONTROLS[:3]
        _setup_full_intersection(
            respx,
            target_count=500,
            combined_count=3,
            combined_gene_ids=hit_ids,
        )

        api = _make_api()
        find_rt = AsyncMock(side_effect=lambda ctx: ctx.record_type)
        with patch(PATCH_TARGET, return_value=api), patch(PATCH_FIND_RT, find_rt):
            result = await _run_intersection_control(
                _common_config(), controls_ids=POSITIVE_CONTROLS
            )

        assert result["targetStepId"] == TARGET_STEP_ID
        assert result["targetResultCount"] == 500
        assert result["controlsCount"] == len(POSITIVE_CONTROLS)
        assert result["intersectionCount"] == 3
        assert isinstance(result["intersectionIds"], list)
        assert set(result["intersectionIds"]) == set(hit_ids)

    @respx.mock
    @pytest.mark.asyncio
    async def test_negative_controls_low_intersection(self) -> None:
        """Negative controls should have low or no intersection hits."""
        _setup_full_intersection(
            respx,
            target_count=500,
            combined_count=0,
            combined_gene_ids=[],
        )

        api = _make_api()
        find_rt = AsyncMock(side_effect=lambda ctx: ctx.record_type)
        with patch(PATCH_TARGET, return_value=api), patch(PATCH_FIND_RT, find_rt):
            result = await _run_intersection_control(
                _common_config(), controls_ids=NEGATIVE_CONTROLS
            )

        assert result["intersectionCount"] == 0
        assert result["intersectionIds"] == []
        assert result["controlsCount"] == len(NEGATIVE_CONTROLS)

    @respx.mock
    @pytest.mark.asyncio
    async def test_strategy_deleted_after_run(self) -> None:
        """Cleanup: the temporary strategy is deleted after the run."""
        _setup_full_intersection(
            respx,
            target_count=100,
            combined_count=1,
            combined_gene_ids=POSITIVE_CONTROLS[:1],
        )

        api = _make_api()
        find_rt = AsyncMock(side_effect=lambda ctx: ctx.record_type)
        with patch(PATCH_TARGET, return_value=api), patch(PATCH_FIND_RT, find_rt):
            await _run_intersection_control(
                _common_config(), controls_ids=POSITIVE_CONTROLS[:3]
            )

        # Verify that a DELETE was issued against the strategies endpoint
        delete_calls = [
            c
            for c in respx.calls
            if c.request.method == "DELETE" and "strategies" in str(c.request.url)
        ]
        assert len(delete_calls) == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_dataset_uploaded_for_input_dataset_param(self) -> None:
        """When controls param type is input-dataset, IDs are uploaded."""
        _setup_full_intersection(
            respx,
            target_count=100,
            combined_count=2,
            combined_gene_ids=POSITIVE_CONTROLS[:2],
            controls_param_type="input-dataset",
        )

        api = _make_api()
        find_rt = AsyncMock(side_effect=lambda ctx: ctx.record_type)
        with patch(PATCH_TARGET, return_value=api), patch(PATCH_FIND_RT, find_rt):
            await _run_intersection_control(
                _common_config(), controls_ids=POSITIVE_CONTROLS
            )

        dataset_calls = [
            c
            for c in respx.calls
            if "datasets" in str(c.request.url) and c.request.method == "POST"
        ]
        assert len(dataset_calls) == 1
        body = json.loads(dataset_calls[0].request.content)
        assert body["sourceType"] == "idList"
        assert body["sourceContent"]["ids"] == POSITIVE_CONTROLS

    @respx.mock
    @pytest.mark.asyncio
    async def test_no_dataset_for_string_param(self) -> None:
        """When controls param is a string type, no dataset upload happens."""
        _setup_full_intersection(
            respx,
            target_count=100,
            combined_count=1,
            combined_gene_ids=POSITIVE_CONTROLS[:1],
            controls_param_type="string",
        )

        api = _make_api()
        find_rt = AsyncMock(side_effect=lambda ctx: ctx.record_type)
        with patch(PATCH_TARGET, return_value=api), patch(PATCH_FIND_RT, find_rt):
            await _run_intersection_control(
                _common_config(), controls_ids=POSITIVE_CONTROLS[:3]
            )

        dataset_calls = [
            c
            for c in respx.calls
            if "datasets" in str(c.request.url) and c.request.method == "POST"
        ]
        assert len(dataset_calls) == 0


# ===================================================================
# 2. Positive + negative controls together
# ===================================================================
class TestPositiveNegativeControls:
    """Exercises run_positive_negative_controls end-to-end.

    Each control set creates its own target step (WDK cascade-deletes
    all steps when a strategy is deleted). The mock must handle two full
    intersection cycles plus the cleanup call.
    """

    @respx.mock
    @pytest.mark.asyncio
    async def test_both_controls_populated(self) -> None:
        """Both positive and negative results should be populated."""
        pos_hits = POSITIVE_CONTROLS[:3]
        neg_hits = NEGATIVE_CONTROLS[:1]

        _mock_session(respx)
        _mock_searches(respx)
        _mock_search_details(respx, controls_param_type="input-dataset")
        _mock_list_strategies(respx)

        # Step creation: 3 per intersection * 2 = 6 total
        respx.post(f"{BASE}/users/{USER_ID}/steps").mock(
            side_effect=[
                _resp(200, step_creation_response(TARGET_STEP_ID)),
                _resp(200, step_creation_response(CONTROLS_STEP_ID)),
                _resp(200, step_creation_response(COMBINED_STEP_ID)),
                _resp(200, step_creation_response(TARGET_STEP_ID + 10)),
                _resp(200, step_creation_response(CONTROLS_STEP_ID + 10)),
                _resp(200, step_creation_response(COMBINED_STEP_ID + 10)),
            ]
        )

        # Dataset creation: twice (once per control set)
        respx.post(f"{BASE}/users/{USER_ID}/datasets").mock(
            side_effect=[
                _resp(200, dataset_creation_response(DATASET_ID)),
                _resp(200, dataset_creation_response(DATASET_ID + 1)),
            ]
        )

        # Strategy creation: twice
        pos_strat_id = STRATEGY_ID
        neg_strat_id = STRATEGY_ID + 10
        respx.post(f"{BASE}/users/{USER_ID}/strategies").mock(
            side_effect=[
                _resp(200, strategy_creation_response(pos_strat_id)),
                _resp(200, strategy_creation_response(neg_strat_id)),
            ]
        )

        # Report calls in order:
        # Positive: target count, combined count, combined answer
        # Negative: target count, combined count, combined answer
        respx.post(url__regex=rf".*/users/{USER_ID}/steps/\d+/reports/standard").mock(
            side_effect=[
                _resp(200, standard_report_response([], 500)),
                _resp(200, standard_report_response([], len(pos_hits))),
                _resp(200, standard_report_response(pos_hits, len(pos_hits))),
                _resp(200, standard_report_response([], 500)),
                _resp(200, standard_report_response([], len(neg_hits))),
                _resp(200, standard_report_response(neg_hits, len(neg_hits))),
            ]
        )

        # Strategy deletion: twice
        respx.delete(url__regex=rf".*/users/{USER_ID}/strategies/\d+").mock(
            side_effect=[
                _resp(204),
                _resp(204),
            ]
        )

        find_rt = AsyncMock(side_effect=lambda ctx: ctx.record_type)
        with (
            patch(PATCH_TARGET, side_effect=lambda sid: _make_api()),
            patch(PATCH_FIND_RT, find_rt),
        ):
            result = await run_positive_negative_controls(
                _common_config(),
                positive_controls=POSITIVE_CONTROLS,
                negative_controls=NEGATIVE_CONTROLS,
            )

        assert result["siteId"] == SITE_ID
        assert result["recordType"] == RECORD_TYPE

        target = result["target"]
        assert isinstance(target, dict)
        assert target["stepId"] == TARGET_STEP_ID
        assert target["resultCount"] == 500

        pos = result["positive"]
        assert isinstance(pos, dict)
        assert pos["controlsCount"] == len(POSITIVE_CONTROLS)
        assert pos["intersectionCount"] == len(pos_hits)
        assert pos["recall"] == len(pos_hits) / len(POSITIVE_CONTROLS)
        assert "missingIdsSample" in pos
        missing = pos["missingIdsSample"]
        expected_missing = [x for x in POSITIVE_CONTROLS if x not in set(pos_hits)]
        assert set(missing) == set(expected_missing)

        neg = result["negative"]
        assert isinstance(neg, dict)
        assert neg["controlsCount"] == len(NEGATIVE_CONTROLS)
        assert neg["intersectionCount"] == len(neg_hits)
        assert neg["falsePositiveRate"] == len(neg_hits) / len(NEGATIVE_CONTROLS)
        assert "unexpectedHitsSample" in neg

    @respx.mock
    @pytest.mark.asyncio
    async def test_positive_only(self) -> None:
        """When only positive controls are provided, negative is None."""
        pos_hits = POSITIVE_CONTROLS[:2]

        _mock_session(respx)
        _mock_searches(respx)
        _mock_search_details(respx, controls_param_type="input-dataset")
        _mock_list_strategies(respx)

        respx.post(f"{BASE}/users/{USER_ID}/steps").mock(
            side_effect=[
                _resp(200, step_creation_response(TARGET_STEP_ID)),
                _resp(200, step_creation_response(CONTROLS_STEP_ID)),
                _resp(200, step_creation_response(COMBINED_STEP_ID)),
            ]
        )
        respx.post(f"{BASE}/users/{USER_ID}/datasets").respond(
            200, json=dataset_creation_response(DATASET_ID)
        )
        respx.post(f"{BASE}/users/{USER_ID}/strategies").respond(
            200, json=strategy_creation_response(STRATEGY_ID)
        )
        respx.post(url__regex=rf".*/users/{USER_ID}/steps/\d+/reports/standard").mock(
            side_effect=[
                _resp(200, standard_report_response([], 500)),
                _resp(200, standard_report_response([], len(pos_hits))),
                _resp(200, standard_report_response(pos_hits, len(pos_hits))),
            ]
        )
        respx.delete(url__regex=rf".*/users/{USER_ID}/strategies/\d+").respond(204)

        find_rt = AsyncMock(side_effect=lambda ctx: ctx.record_type)
        with (
            patch(PATCH_TARGET, side_effect=lambda sid: _make_api()),
            patch(PATCH_FIND_RT, find_rt),
        ):
            result = await run_positive_negative_controls(
                _common_config(),
                positive_controls=POSITIVE_CONTROLS,
            )

        assert result["positive"] is not None
        assert result["negative"] is None


# ===================================================================
# 3. Error handling -- WDK returns 422/500
# ===================================================================
class TestErrorHandling:
    """Verify error propagation when WDK returns error status codes."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_step_creation_422_propagates(self) -> None:
        """WDK 422 on step creation raises WDKError."""
        _mock_session(respx)
        _mock_search_details(respx)

        respx.post(f"{BASE}/users/{USER_ID}/steps").respond(
            422,
            json={
                "status": "unprocessable_entity",
                "message": "Validation failed",
                "errors": {"byKey": {"fold_change": ["Invalid value"]}},
            },
        )

        api = _make_api()
        find_rt = AsyncMock(side_effect=lambda ctx: ctx.record_type)
        with (
            patch(PATCH_TARGET, return_value=api),
            patch(PATCH_FIND_RT, find_rt),
            pytest.raises(WDKError) as exc_info,
        ):
            await _run_intersection_control(
                _common_config(), controls_ids=POSITIVE_CONTROLS
            )

        assert exc_info.value.status == 422

    @respx.mock
    @pytest.mark.asyncio
    async def test_strategy_creation_500_propagates(self) -> None:
        """WDK 500 on strategy creation raises WDKError, cleanup still runs."""
        _mock_session(respx)
        _mock_searches(respx)
        _mock_search_details(respx, controls_param_type="input-dataset")

        respx.post(f"{BASE}/users/{USER_ID}/steps").mock(
            side_effect=[
                _resp(200, step_creation_response(TARGET_STEP_ID)),
                _resp(200, step_creation_response(CONTROLS_STEP_ID)),
                _resp(200, step_creation_response(COMBINED_STEP_ID)),
            ]
        )
        respx.post(f"{BASE}/users/{USER_ID}/datasets").respond(
            200, json=dataset_creation_response(DATASET_ID)
        )

        respx.post(f"{BASE}/users/{USER_ID}/strategies").respond(
            500, json={"status": "server_error", "message": "Internal error"}
        )

        api = _make_api()
        find_rt = AsyncMock(side_effect=lambda ctx: ctx.record_type)
        with (
            patch(PATCH_TARGET, return_value=api),
            patch(PATCH_FIND_RT, find_rt),
            pytest.raises(WDKError) as exc_info,
        ):
            await _run_intersection_control(
                _common_config(), controls_ids=POSITIVE_CONTROLS
            )

        assert exc_info.value.status == 500

    @respx.mock
    @pytest.mark.asyncio
    async def test_report_error_caught_gracefully(self) -> None:
        """WDK error on step count is caught; strategy is still deleted."""
        _mock_session(respx)
        _mock_searches(respx)
        _mock_search_details(respx, controls_param_type="input-dataset")

        respx.post(f"{BASE}/users/{USER_ID}/steps").mock(
            side_effect=[
                _resp(200, step_creation_response(TARGET_STEP_ID)),
                _resp(200, step_creation_response(CONTROLS_STEP_ID)),
                _resp(200, step_creation_response(COMBINED_STEP_ID)),
            ]
        )
        respx.post(f"{BASE}/users/{USER_ID}/datasets").respond(
            200, json=dataset_creation_response(DATASET_ID)
        )
        respx.post(f"{BASE}/users/{USER_ID}/strategies").respond(
            200, json=strategy_creation_response(STRATEGY_ID)
        )

        # Target count returns 500 error -> retried 3x by tenacity -> WDKError -> None
        # Combined count returns 500 error -> retried 3x by tenacity -> WDKError -> None
        # get_step_answer returns records
        respx.post(url__regex=rf".*/users/{USER_ID}/steps/\d+/reports/standard").mock(
            side_effect=[
                # Target count: 3 attempts (initial + 2 retries), all 500
                _resp(500, {"message": "target count failed"}),
                _resp(500, {"message": "target count failed"}),
                _resp(500, {"message": "target count failed"}),
                # Combined count: 3 attempts (initial + 2 retries), all 500
                _resp(500, {"message": "combined count failed"}),
                _resp(500, {"message": "combined count failed"}),
                _resp(500, {"message": "combined count failed"}),
                # get_step_answer succeeds
                _resp(200, standard_report_response(POSITIVE_CONTROLS[:2], 2)),
            ]
        )

        respx.delete(f"{BASE}/users/{USER_ID}/strategies/{STRATEGY_ID}").respond(204)

        api = _make_api()
        find_rt = AsyncMock(side_effect=lambda ctx: ctx.record_type)
        with patch(PATCH_TARGET, return_value=api), patch(PATCH_FIND_RT, find_rt):
            result = await _run_intersection_control(
                _common_config(), controls_ids=POSITIVE_CONTROLS
            )

        # Counts are None because the 500 was caught by _get_total_count_for_step
        assert result["targetResultCount"] is None
        assert result["intersectionCount"] is None

        # Strategy was still cleaned up
        delete_calls = [
            c
            for c in respx.calls
            if c.request.method == "DELETE" and "strategies" in str(c.request.url)
        ]
        assert len(delete_calls) == 1


# ===================================================================
# 4. Empty results -- target search returns 0 results
# ===================================================================
class TestEmptyResults:
    """When the target search returns 0 results, intersection should be 0."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_zero_target_results(self) -> None:
        """With 0 target results, intersection is 0 for both pos and neg."""
        _mock_session(respx)
        _mock_searches(respx)
        _mock_search_details(respx, controls_param_type="input-dataset")
        _mock_list_strategies(respx)

        respx.post(f"{BASE}/users/{USER_ID}/steps").mock(
            side_effect=[
                _resp(200, step_creation_response(TARGET_STEP_ID)),
                _resp(200, step_creation_response(CONTROLS_STEP_ID)),
                _resp(200, step_creation_response(COMBINED_STEP_ID)),
                _resp(200, step_creation_response(TARGET_STEP_ID + 10)),
                _resp(200, step_creation_response(CONTROLS_STEP_ID + 10)),
                _resp(200, step_creation_response(COMBINED_STEP_ID + 10)),
            ]
        )
        respx.post(f"{BASE}/users/{USER_ID}/datasets").mock(
            side_effect=[
                _resp(200, dataset_creation_response(DATASET_ID)),
                _resp(200, dataset_creation_response(DATASET_ID + 1)),
            ]
        )
        respx.post(f"{BASE}/users/{USER_ID}/strategies").mock(
            side_effect=[
                _resp(200, strategy_creation_response(STRATEGY_ID)),
                _resp(200, strategy_creation_response(STRATEGY_ID + 10)),
            ]
        )

        empty = standard_report_response([], 0)
        respx.post(url__regex=rf".*/users/{USER_ID}/steps/\d+/reports/standard").mock(
            side_effect=[
                # Positive: target count, combined count, combined answer
                _resp(200, empty),
                _resp(200, empty),
                _resp(200, empty),
                # Negative: target count, combined count, combined answer
                _resp(200, empty),
                _resp(200, empty),
                _resp(200, empty),
            ]
        )
        respx.delete(url__regex=rf".*/users/{USER_ID}/strategies/\d+").mock(
            side_effect=[_resp(204), _resp(204)]
        )

        find_rt = AsyncMock(side_effect=lambda ctx: ctx.record_type)
        with (
            patch(PATCH_TARGET, side_effect=lambda sid: _make_api()),
            patch(PATCH_FIND_RT, find_rt),
        ):
            result = await run_positive_negative_controls(
                _common_config(),
                positive_controls=POSITIVE_CONTROLS,
                negative_controls=NEGATIVE_CONTROLS,
            )

        target = result["target"]
        assert isinstance(target, dict)
        assert target["resultCount"] == 0

        pos = result["positive"]
        assert isinstance(pos, dict)
        assert pos["intersectionCount"] == 0
        assert pos["intersectionIds"] == []
        assert pos["recall"] == 0.0

        neg = result["negative"]
        assert isinstance(neg, dict)
        assert neg["intersectionCount"] == 0
        assert neg["intersectionIds"] == []
        assert neg["falsePositiveRate"] == 0.0

    @respx.mock
    @pytest.mark.asyncio
    async def test_single_intersection_zero_results(self) -> None:
        """A single _run_intersection_control with 0 target results."""
        _setup_full_intersection(
            respx,
            target_count=0,
            combined_count=0,
            combined_gene_ids=[],
        )

        api = _make_api()
        find_rt = AsyncMock(side_effect=lambda ctx: ctx.record_type)
        with patch(PATCH_TARGET, return_value=api), patch(PATCH_FIND_RT, find_rt):
            result = await _run_intersection_control(
                _common_config(), controls_ids=POSITIVE_CONTROLS
            )

        assert result["targetResultCount"] == 0
        assert result["intersectionCount"] == 0
        assert result["intersectionIds"] == []
        assert result["controlsCount"] == len(POSITIVE_CONTROLS)

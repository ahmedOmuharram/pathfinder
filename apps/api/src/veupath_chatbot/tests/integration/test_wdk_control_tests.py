"""Integration tests for the control_tests module.

Mocks the ``StrategyAPI`` returned by ``get_strategy_api`` so that every test
exercises the full ``run_positive_negative_controls`` / ``_run_intersection_control``
logic (step creation, param-type resolution, dataset upload, strategy lifecycle,
answer extraction) without hitting a real WDK deployment.

Fixture responses come from
``veupath_chatbot.tests.fixtures.wdk_responses``.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from veupath_chatbot.platform.errors import InternalError
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.control_helpers import _encode_id_list
from veupath_chatbot.services.control_tests import (
    IntersectionConfig,
    _run_intersection_control,
    resolve_controls_param_type,
    run_positive_negative_controls,
)
from veupath_chatbot.services.wdk.helpers import extract_record_ids
from veupath_chatbot.tests.fixtures.wdk_responses import (
    standard_report_response,
    step_creation_response,
    strategy_creation_response,
)

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------
SITE_ID = "plasmodb"
RECORD_TYPE = "gene"
TARGET_SEARCH_NAME = "GenesByTaxon"
TARGET_PARAMETERS: JSONObject = {"organism": '["Plasmodium falciparum 3D7"]'}
CONTROLS_SEARCH_NAME = "GeneByLocusTag"
CONTROLS_PARAM_NAME = "ds_gene_ids"

GENE_IDS: list[str] = [
    "PF3D7_0100100",
    "PF3D7_0831900",
    "PF3D7_1133400",
    "PF3D7_0709000",
    "PF3D7_1343700",
]

POSITIVE_IDS = GENE_IDS[:3]
NEGATIVE_IDS = GENE_IDS[3:]

# Step / strategy IDs returned by mock
TARGET_STEP_ID = 100
CONTROLS_STEP_ID = 101
COMBINED_STEP_ID = 102
STRATEGY_ID = 200
DATASET_ID = 500

PATCH_TARGET = "veupath_chatbot.services.control_tests.get_strategy_api"
PATCH_RECORD_TYPE = "veupath_chatbot.services.control_tests.find_record_type_for_search"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_mock_api(
    *,
    target_count: int = 150,
    combined_count: int = 3,
    answer_gene_ids: list[str] | None = None,
    param_type: str | None = None,
    stale_strategies: list[dict] | None = None,
) -> AsyncMock:
    """Build a mock ``StrategyAPI`` with sensible defaults.

    The returned mock supports the full lifecycle exercised by
    ``_run_intersection_control``:
    list_strategies, create_step (x2), resolve param type,
    optional create_dataset, create_combined_step, create_strategy,
    get_step_count (x2), get_step_answer, delete_strategy.
    """
    api = AsyncMock()

    # list_strategies -> used by _cleanup_internal_control_test_strategies
    api.list_strategies.return_value = stale_strategies or []

    # create_step returns different IDs on successive calls.
    # First call = target step, second call = controls step.
    api.create_step.side_effect = [
        step_creation_response(TARGET_STEP_ID),
        step_creation_response(CONTROLS_STEP_ID),
    ]

    # Param type resolution (via api.client.get_search_details)
    # Build a search_details response with the controls param having the
    # requested type.
    resolved_type = param_type or "string"
    api.client = MagicMock()
    api.client.get_search_details = AsyncMock(
        return_value={
            "searchData": {
                "parameters": [
                    {"name": CONTROLS_PARAM_NAME, "type": resolved_type},
                ],
            },
        }
    )

    # create_dataset (only called when param_type == "input-dataset")
    api.create_dataset.return_value = DATASET_ID

    # create_combined_step
    api.create_combined_step.return_value = step_creation_response(COMBINED_STEP_ID)

    # create_strategy
    api.create_strategy.return_value = strategy_creation_response(STRATEGY_ID)

    # get_step_count: first call = target count, second call = combined count
    api.get_step_count.side_effect = [target_count, combined_count]

    # get_step_answer: returns the intersection records
    ids = answer_gene_ids if answer_gene_ids is not None else GENE_IDS[:combined_count]
    api.get_step_answer.return_value = standard_report_response(ids, combined_count)

    # delete_strategy is a no-op
    api.delete_strategy.return_value = None

    return api


def _make_intersection_config() -> IntersectionConfig:
    """Return an IntersectionConfig with test defaults."""
    return IntersectionConfig(
        site_id=SITE_ID,
        record_type=RECORD_TYPE,
        target_search_name=TARGET_SEARCH_NAME,
        target_parameters=TARGET_PARAMETERS,
        controls_search_name=CONTROLS_SEARCH_NAME,
        controls_param_name=CONTROLS_PARAM_NAME,
        controls_value_format="newline",
        controls_extra_parameters=None,
    )


# ===================================================================
# Unit-level helpers (_encode_id_list, extract_record_ids)
# ===================================================================
class TestEncodeIdList:
    def test_newline_format(self) -> None:
        assert (
            _encode_id_list(GENE_IDS[:2], "newline") == "PF3D7_0100100\nPF3D7_0831900"
        )

    def test_comma_format(self) -> None:
        assert _encode_id_list(GENE_IDS[:2], "comma") == "PF3D7_0100100,PF3D7_0831900"

    def test_json_list_format(self) -> None:
        result = _encode_id_list(GENE_IDS[:2], "json_list")
        assert json.loads(result) == GENE_IDS[:2]

    def test_strips_whitespace(self) -> None:
        assert _encode_id_list(["  PF3D7_0100100  ", " PF3D7_0831900 "], "comma") == (
            "PF3D7_0100100,PF3D7_0831900"
        )

    def test_skips_empty_strings(self) -> None:
        assert (
            _encode_id_list(["PF3D7_0100100", "", "  "], "newline") == "PF3D7_0100100"
        )


class TestExtractRecordIds:
    def test_extracts_from_primary_key(self) -> None:
        records = standard_report_response(GENE_IDS[:2])["records"]
        assert extract_record_ids(records) == GENE_IDS[:2]

    def test_preferred_key_from_attributes(self) -> None:
        records = standard_report_response(GENE_IDS[:2])["records"]
        result = extract_record_ids(records, preferred_key="gene_source_id")
        assert result == GENE_IDS[:2]

    def test_returns_empty_for_non_list(self) -> None:
        assert extract_record_ids(None) == []
        assert extract_record_ids("not a list") == []

    def test_skips_malformed_records(self) -> None:
        records = [{"no_id_field": True}, "not a dict", None]
        assert extract_record_ids(records) == []


# ===================================================================
# resolve_controls_param_type
# ===================================================================
class TestResolveControlsParamType:
    @pytest.mark.asyncio
    async def test_returns_param_type(self) -> None:
        api = AsyncMock()
        api.client = MagicMock()
        api.client.get_search_details = AsyncMock(
            return_value={
                "searchData": {
                    "parameters": [
                        {"name": "ds_gene_ids", "type": "input-dataset"},
                    ],
                },
            }
        )
        result = await resolve_controls_param_type(
            api, RECORD_TYPE, CONTROLS_SEARCH_NAME, CONTROLS_PARAM_NAME
        )
        assert result == "input-dataset"

    @pytest.mark.asyncio
    async def test_returns_none_when_param_not_found(self) -> None:
        api = AsyncMock()
        api.client = MagicMock()
        api.client.get_search_details = AsyncMock(
            return_value={
                "searchData": {
                    "parameters": [
                        {"name": "other_param", "type": "string"},
                    ],
                },
            }
        )
        result = await resolve_controls_param_type(
            api, RECORD_TYPE, CONTROLS_SEARCH_NAME, CONTROLS_PARAM_NAME
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self) -> None:
        api = AsyncMock()
        api.client = MagicMock()
        api.client.get_search_details = AsyncMock(side_effect=ValueError("boom"))
        result = await resolve_controls_param_type(
            api, RECORD_TYPE, CONTROLS_SEARCH_NAME, CONTROLS_PARAM_NAME
        )
        assert result is None


# ===================================================================
# _run_intersection_control (positive controls flow)
# ===================================================================
class TestPositiveControlsIntersection:
    """Exercises the happy path: target -> controls -> combine -> strategy -> answer."""

    @pytest.mark.asyncio
    async def test_returns_correct_structure(self) -> None:
        mock_api = _make_mock_api(
            target_count=150,
            combined_count=3,
            answer_gene_ids=POSITIVE_IDS,
        )
        config = _make_intersection_config()
        with (
            patch(PATCH_TARGET, return_value=mock_api),
            patch(PATCH_RECORD_TYPE, return_value=RECORD_TYPE),
        ):
            result = await _run_intersection_control(config, POSITIVE_IDS)

        assert result["targetStepId"] == TARGET_STEP_ID
        assert result["targetResultCount"] == 150
        assert result["controlsCount"] == len(POSITIVE_IDS)
        assert result["intersectionCount"] == 3

    @pytest.mark.asyncio
    async def test_creates_steps_in_order(self) -> None:
        mock_api = _make_mock_api(combined_count=2, answer_gene_ids=POSITIVE_IDS[:2])
        config = _make_intersection_config()
        with (
            patch(PATCH_TARGET, return_value=mock_api),
            patch(PATCH_RECORD_TYPE, return_value=RECORD_TYPE),
        ):
            await _run_intersection_control(config, POSITIVE_IDS)

        # Two create_step calls: target then controls
        assert mock_api.create_step.call_count == 2
        first_call = mock_api.create_step.call_args_list[0]
        assert first_call.kwargs["custom_name"] == "Target"
        second_call = mock_api.create_step.call_args_list[1]
        assert second_call.kwargs["custom_name"] == "Controls"

    @pytest.mark.asyncio
    async def test_creates_strategy_and_queries_answer(self) -> None:
        mock_api = _make_mock_api(combined_count=2, answer_gene_ids=POSITIVE_IDS[:2])
        config = _make_intersection_config()
        with (
            patch(PATCH_TARGET, return_value=mock_api),
            patch(PATCH_RECORD_TYPE, return_value=RECORD_TYPE),
        ):
            await _run_intersection_control(config, POSITIVE_IDS)

        mock_api.create_strategy.assert_awaited_once()
        mock_api.get_step_answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_intersection_ids_returned(self) -> None:
        """The result should contain the IDs found in the intersection."""
        mock_api = _make_mock_api(combined_count=2, answer_gene_ids=POSITIVE_IDS[:2])
        config = _make_intersection_config()
        with (
            patch(PATCH_TARGET, return_value=mock_api),
            patch(PATCH_RECORD_TYPE, return_value=RECORD_TYPE),
        ):
            result = await _run_intersection_control(config, POSITIVE_IDS)

        ids = result["intersectionIds"]
        assert isinstance(ids, list)
        assert set(ids) == set(POSITIVE_IDS[:2])


# ===================================================================
# _run_intersection_control (negative controls flow)
# ===================================================================
class TestNegativeControls:
    """Negative controls follow the same code path but use different IDs."""

    @pytest.mark.asyncio
    async def test_negative_controls_intersection(self) -> None:
        mock_api = _make_mock_api(
            target_count=150,
            combined_count=1,
            answer_gene_ids=NEGATIVE_IDS[:1],
        )
        config = _make_intersection_config()
        with (
            patch(PATCH_TARGET, return_value=mock_api),
            patch(PATCH_RECORD_TYPE, return_value=RECORD_TYPE),
        ):
            result = await _run_intersection_control(config, NEGATIVE_IDS)

        assert result["targetStepId"] == TARGET_STEP_ID
        assert result["controlsCount"] == len(NEGATIVE_IDS)
        assert result["intersectionCount"] == 1
        assert result["intersectionIds"] == NEGATIVE_IDS[:1]

    @pytest.mark.asyncio
    async def test_zero_intersection(self) -> None:
        """When no negative controls appear in target results, count is zero."""
        mock_api = _make_mock_api(
            target_count=150,
            combined_count=0,
            answer_gene_ids=[],
        )
        config = _make_intersection_config()
        with (
            patch(PATCH_TARGET, return_value=mock_api),
            patch(PATCH_RECORD_TYPE, return_value=RECORD_TYPE),
        ):
            result = await _run_intersection_control(config, NEGATIVE_IDS)

        assert result["intersectionCount"] == 0
        assert result["intersectionIds"] == []


# ===================================================================
# run_positive_negative_controls (both sets)
# ===================================================================
class TestBothControls:
    """Tests ``run_positive_negative_controls`` with both sets in one call.

    Each control set creates its OWN strategy API via ``get_strategy_api``,
    so we need the mock to be called twice (once for positive, once for
    negative) — each returning a fresh mock with its own side_effect chain.
    """

    @pytest.mark.asyncio
    async def test_positive_and_negative_together(self) -> None:
        """Both positive and negative results should be populated."""
        cleanup_api = _make_mock_api()
        pos_api = _make_mock_api(
            target_count=150,
            combined_count=3,
            answer_gene_ids=POSITIVE_IDS,
        )
        neg_api = _make_mock_api(
            target_count=150,
            combined_count=1,
            answer_gene_ids=NEGATIVE_IDS[:1],
        )
        config = _make_intersection_config()
        with (
            patch(PATCH_TARGET, side_effect=[cleanup_api, pos_api, neg_api]),
            patch(PATCH_RECORD_TYPE, return_value=RECORD_TYPE),
        ):
            result = await run_positive_negative_controls(
                config,
                positive_controls=POSITIVE_IDS,
                negative_controls=NEGATIVE_IDS,
            )

        assert result["siteId"] == SITE_ID
        assert result["recordType"] == RECORD_TYPE

        target = result["target"]
        assert isinstance(target, dict)
        assert target["stepId"] == TARGET_STEP_ID
        assert target["resultCount"] == 150

        pos = result["positive"]
        assert isinstance(pos, dict)
        assert pos["controlsCount"] == len(POSITIVE_IDS)
        assert pos["intersectionCount"] == 3
        assert pos["recall"] == 3 / len(POSITIVE_IDS)
        assert "missingIdsSample" in pos

        neg = result["negative"]
        assert isinstance(neg, dict)
        assert neg["controlsCount"] == len(NEGATIVE_IDS)
        assert neg["intersectionCount"] == 1
        assert neg["falsePositiveRate"] == 1 / len(NEGATIVE_IDS)
        assert "unexpectedHitsSample" in neg

    @pytest.mark.asyncio
    async def test_positive_only(self) -> None:
        """When only positive controls are provided, negative is None."""
        mock_api = _make_mock_api(
            target_count=150,
            combined_count=2,
            answer_gene_ids=POSITIVE_IDS[:2],
        )
        config = _make_intersection_config()
        with (
            patch(PATCH_TARGET, return_value=mock_api),
            patch(PATCH_RECORD_TYPE, return_value=RECORD_TYPE),
        ):
            result = await run_positive_negative_controls(
                config,
                positive_controls=POSITIVE_IDS,
                negative_controls=None,
            )

        assert result["positive"] is not None
        assert result["negative"] is None

    @pytest.mark.asyncio
    async def test_negative_only(self) -> None:
        """When only negative controls are provided, positive is None."""
        mock_api = _make_mock_api(
            target_count=150,
            combined_count=0,
            answer_gene_ids=[],
        )
        config = _make_intersection_config()
        with (
            patch(PATCH_TARGET, return_value=mock_api),
            patch(PATCH_RECORD_TYPE, return_value=RECORD_TYPE),
        ):
            result = await run_positive_negative_controls(
                config,
                positive_controls=None,
                negative_controls=NEGATIVE_IDS,
            )

        assert result["positive"] is None
        assert result["negative"] is not None

    @pytest.mark.asyncio
    async def test_both_empty_returns_nulls(self) -> None:
        """When neither set is provided, both are None — no API calls."""
        config = _make_intersection_config()
        with (
            patch(PATCH_TARGET) as mock_factory,
            patch(PATCH_RECORD_TYPE, return_value=RECORD_TYPE),
        ):
            result = await run_positive_negative_controls(
                config,
                positive_controls=[],
                negative_controls=[],
                skip_cleanup=True,
            )

        mock_factory.assert_not_called()
        assert result["positive"] is None
        assert result["negative"] is None

    @pytest.mark.asyncio
    async def test_missing_ids_sample_populated(self) -> None:
        """Positive controls not found in intersection appear in missingIdsSample."""
        # Only the first ID is in the intersection; the rest are "missing"
        found_ids = POSITIVE_IDS[:1]
        mock_api = _make_mock_api(
            target_count=150,
            combined_count=1,
            answer_gene_ids=found_ids,
        )
        config = _make_intersection_config()
        with (
            patch(PATCH_TARGET, return_value=mock_api),
            patch(PATCH_RECORD_TYPE, return_value=RECORD_TYPE),
        ):
            result = await run_positive_negative_controls(
                config,
                positive_controls=POSITIVE_IDS,
            )

        pos = result["positive"]
        assert isinstance(pos, dict)
        missing = pos["missingIdsSample"]
        assert isinstance(missing, list)
        # The IDs NOT found in the intersection should appear as missing
        expected_missing = [x for x in POSITIVE_IDS if x not in found_ids]
        assert set(missing) == set(expected_missing)


# ===================================================================
# Dataset param path (input-dataset)
# ===================================================================
class TestControlsWithDatasetParam:
    """When the controls parameter type is ``input-dataset``, the module
    uploads IDs via ``create_dataset`` and passes the dataset ID instead
    of raw ID text.
    """

    @pytest.mark.asyncio
    async def test_creates_dataset_when_input_dataset_type(self) -> None:
        mock_api = _make_mock_api(
            combined_count=2,
            answer_gene_ids=POSITIVE_IDS[:2],
            param_type="input-dataset",
        )
        config = _make_intersection_config()
        with (
            patch(PATCH_TARGET, return_value=mock_api),
            patch(PATCH_RECORD_TYPE, return_value=RECORD_TYPE),
        ):
            await _run_intersection_control(config, POSITIVE_IDS)

        mock_api.create_dataset.assert_awaited_once_with(POSITIVE_IDS)

        # The controls step should have received the dataset ID as the param value
        controls_call = mock_api.create_step.call_args_list[1]
        params = controls_call.kwargs.get("parameters", {})
        assert params[CONTROLS_PARAM_NAME] == str(DATASET_ID)

    @pytest.mark.asyncio
    async def test_no_dataset_for_string_type(self) -> None:
        """Non-dataset param types should use the raw encoded ID list."""
        mock_api = _make_mock_api(
            combined_count=2,
            answer_gene_ids=POSITIVE_IDS[:2],
            param_type="string",
        )
        config = _make_intersection_config()
        with (
            patch(PATCH_TARGET, return_value=mock_api),
            patch(PATCH_RECORD_TYPE, return_value=RECORD_TYPE),
        ):
            await _run_intersection_control(config, POSITIVE_IDS)

        mock_api.create_dataset.assert_not_awaited()

        # The controls step should have received the raw newline-encoded IDs
        controls_call = mock_api.create_step.call_args_list[1]
        params = controls_call.kwargs.get("parameters", {})
        assert params[CONTROLS_PARAM_NAME] == "\n".join(POSITIVE_IDS)


# ===================================================================
# Cleanup behaviour
# ===================================================================
class TestCleanupOnSuccess:
    """After a successful run, the temporary strategy MUST be deleted."""

    @pytest.mark.asyncio
    async def test_strategy_deleted_after_success(self) -> None:
        mock_api = _make_mock_api(combined_count=2, answer_gene_ids=POSITIVE_IDS[:2])
        config = _make_intersection_config()
        with (
            patch(PATCH_TARGET, return_value=mock_api),
            patch(PATCH_RECORD_TYPE, return_value=RECORD_TYPE),
        ):
            await _run_intersection_control(config, POSITIVE_IDS)

        mock_api.delete_strategy.assert_awaited_once_with(STRATEGY_ID)

    @pytest.mark.asyncio
    async def test_stale_strategies_cleaned_up(self) -> None:
        """Stale internal strategies from previous interrupted runs are deleted."""
        stale = [
            {
                "name": "__pathfinder_internal__:Pathfinder control test",
                "strategyId": 999,
            },
        ]
        cleanup_api = _make_mock_api(stale_strategies=stale)
        pos_api = _make_mock_api(
            combined_count=2,
            answer_gene_ids=POSITIVE_IDS[:2],
        )
        config = _make_intersection_config()
        with (
            patch(PATCH_TARGET, side_effect=[cleanup_api, pos_api]),
            patch(PATCH_RECORD_TYPE, return_value=RECORD_TYPE),
        ):
            await run_positive_negative_controls(
                config,
                positive_controls=POSITIVE_IDS,
            )

        # The stale strategy should have been deleted by the cleanup API
        cleanup_api.delete_strategy.assert_any_await(999)
        # The temp strategy should have been deleted by the pos API
        pos_api.delete_strategy.assert_awaited_once_with(STRATEGY_ID)


class TestCleanupOnFailure:
    """The temporary strategy MUST be deleted even when WDK errors occur."""

    @pytest.mark.asyncio
    async def test_strategy_deleted_on_step_count_error(self) -> None:
        """If get_step_count raises, cleanup still runs."""
        mock_api = _make_mock_api(combined_count=2, answer_gene_ids=POSITIVE_IDS[:2])
        # Make the FIRST get_step_count call (target count) raise.
        # The code catches this via _get_total_count_for_step and returns None.
        mock_api.get_step_count.side_effect = [
            RuntimeError("WDK 500"),
            2,
        ]
        config = _make_intersection_config()
        with (
            patch(PATCH_TARGET, return_value=mock_api),
            patch(PATCH_RECORD_TYPE, return_value=RECORD_TYPE),
        ):
            result = await _run_intersection_control(config, POSITIVE_IDS)

        # targetResultCount should be None because get_step_count failed
        assert result["targetResultCount"] is None
        # Strategy cleanup still happened
        mock_api.delete_strategy.assert_awaited_once_with(STRATEGY_ID)

    @pytest.mark.asyncio
    async def test_strategy_deleted_on_answer_error(self) -> None:
        """If get_step_answer raises, cleanup still runs."""
        mock_api = _make_mock_api(combined_count=2, answer_gene_ids=POSITIVE_IDS[:2])
        mock_api.get_step_answer.side_effect = RuntimeError("WDK timeout")

        config = _make_intersection_config()
        with (
            patch(PATCH_TARGET, return_value=mock_api),
            patch(PATCH_RECORD_TYPE, return_value=RECORD_TYPE),
            pytest.raises(RuntimeError, match="WDK timeout"),
        ):
            await _run_intersection_control(config, POSITIVE_IDS)

        mock_api.delete_strategy.assert_awaited_once_with(STRATEGY_ID)

    @pytest.mark.asyncio
    async def test_cleanup_failure_does_not_mask_original_error(self) -> None:
        """If delete_strategy itself fails, the original error still propagates."""
        mock_api = _make_mock_api(combined_count=2, answer_gene_ids=POSITIVE_IDS[:2])
        mock_api.get_step_answer.side_effect = RuntimeError("original error")
        mock_api.delete_strategy.side_effect = RuntimeError("cleanup also failed")

        config = _make_intersection_config()
        with (
            patch(PATCH_TARGET, return_value=mock_api),
            patch(PATCH_RECORD_TYPE, return_value=RECORD_TYPE),
            pytest.raises(RuntimeError, match="original error"),
        ):
            await _run_intersection_control(config, POSITIVE_IDS)

    @pytest.mark.asyncio
    async def test_no_cleanup_when_strategy_creation_fails(self) -> None:
        """If create_strategy fails (returns no id), delete is not attempted."""
        mock_api = _make_mock_api(combined_count=2, answer_gene_ids=POSITIVE_IDS[:2])
        # Return a response without an id -> temp_strategy_id stays None
        mock_api.create_strategy.return_value = {}

        config = _make_intersection_config()
        with (
            patch(PATCH_TARGET, return_value=mock_api),
            patch(PATCH_RECORD_TYPE, return_value=RECORD_TYPE),
        ):
            # get_step_count will raise because steps are not in a strategy,
            # but _get_total_count_for_step catches it. get_step_answer will
            # return a result (mock doesn't enforce strategy existence).
            await _run_intersection_control(config, POSITIVE_IDS)

        # delete_strategy should NOT have been called (no strategy ID to delete,
        # beyond any stale cleanup)
        mock_api.delete_strategy.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_target_step_creation_failure_raises(self) -> None:
        """If the target step creation returns no id, InternalError is raised."""
        mock_api = _make_mock_api()
        mock_api.create_step.side_effect = [
            {},  # target step with no id
            step_creation_response(CONTROLS_STEP_ID),
        ]
        config = _make_intersection_config()
        with (
            patch(PATCH_TARGET, return_value=mock_api),
            patch(PATCH_RECORD_TYPE, return_value=RECORD_TYPE),
            pytest.raises(InternalError) as exc_info,
        ):
            await _run_intersection_control(config, POSITIVE_IDS)
        assert "target step" in (exc_info.value.detail or "")

    @pytest.mark.asyncio
    async def test_controls_step_creation_failure_raises(self) -> None:
        """If the controls step creation returns no id, InternalError is raised."""
        mock_api = _make_mock_api()
        mock_api.create_step.side_effect = [
            step_creation_response(TARGET_STEP_ID),
            {},  # controls step with no id
        ]
        config = _make_intersection_config()
        with (
            patch(PATCH_TARGET, return_value=mock_api),
            patch(PATCH_RECORD_TYPE, return_value=RECORD_TYPE),
            pytest.raises(InternalError) as exc_info,
        ):
            await _run_intersection_control(config, POSITIVE_IDS)
        assert "controls step" in (exc_info.value.detail or "")

    @pytest.mark.asyncio
    async def test_combined_step_creation_failure_raises(self) -> None:
        """If the combined step creation returns no id, InternalError is raised."""
        mock_api = _make_mock_api()
        mock_api.create_combined_step.return_value = {}  # no id

        config = _make_intersection_config()
        with (
            patch(PATCH_TARGET, return_value=mock_api),
            patch(PATCH_RECORD_TYPE, return_value=RECORD_TYPE),
            pytest.raises(InternalError) as exc_info,
        ):
            await _run_intersection_control(config, POSITIVE_IDS)
        assert "combined step" in (exc_info.value.detail or "")

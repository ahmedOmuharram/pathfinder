"""Live integration tests for control tests (intersection-based strategy evaluation)
across MULTIPLE VEuPathDB databases.

Tests _run_intersection_control() and run_positive_negative_controls() against
REAL WDK APIs with REAL gene IDs from four VEuPathDB databases: PlasmoDB,
ToxoDB, FungiDB, and TriTrypDB.

Strategy: Use GenesByTaxon as the target search (returns ALL genes for an
organism). Known genes from that organism serve as positive controls (they
should ALL appear in the intersection). Genes from a DIFFERENT organism
serve as negative controls (they should NOT appear).

NO MOCKS. All calls hit live WDK endpoints.

Requires network access to VEuPathDB sites. Run with:

    pytest src/veupath_chatbot/tests/integration/test_live_controls_multi_db.py -v -s

Skip with:

    pytest -m "not live_wdk"
"""

from collections.abc import AsyncGenerator
from typing import cast

import pytest

from veupath_chatbot.integrations.veupathdb.site_router import get_site_router
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.control_tests import (
    IntersectionConfig,
    _run_intersection_control,
    run_positive_negative_controls,
)
from veupath_chatbot.services.experiment.types import ControlTestResult

pytestmark = pytest.mark.live_wdk

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

RECORD_TYPE = "transcript"
CONTROLS_SEARCH_NAME = "GeneByLocusTag"
CONTROLS_PARAM_NAME = "ds_gene_ids"
CONTROLS_VALUE_FORMAT = "newline"

# ---------------------------------------------------------------------------
# Per-database test data
# ---------------------------------------------------------------------------

# -- PlasmoDB --
PLASMO_SITE_ID = "plasmodb"
PLASMO_TARGET_PARAMS: JSONObject = cast(
    "JSONObject", {"organism": "Plasmodium falciparum 3D7"}
)
PLASMO_POSITIVE = [
    "PF3D7_1222600",  # PfAP2-G
    "PF3D7_1031000",  # Pfs25
    "PF3D7_0209000",  # Pfs230
    "PF3D7_1346700",  # Pfs48/45
    "PF3D7_1346800",  # Pfs47
    "PF3D7_0935400",  # CDPK4
    "PF3D7_0406200",  # MDV1/PEG3
    "PF3D7_1408200",  # Pf11-1
    "PF3D7_1216500",  # GEP1
    "PF3D7_1477700",  # HAP2/GCS1
]
PLASMO_NEGATIVE = [
    "TGME49_200010",
    "TGME49_200110",
    "TGME49_200130",
    "TGME49_200230",
    "TGME49_200240",
    "TGME49_200250",
    "TGME49_200260",
    "TGME49_200270",
]

# -- ToxoDB --
TOXO_SITE_ID = "toxodb"
TOXO_TARGET_PARAMS: JSONObject = cast(
    "JSONObject", {"organism": "Toxoplasma gondii ME49"}
)
TOXO_POSITIVE = [
    "TGME49_200010",
    "TGME49_200110",
    "TGME49_200130",
    "TGME49_200230",
    "TGME49_200240",
    "TGME49_200250",
    "TGME49_200260",
    "TGME49_200270",
    "TGME49_200280",
    "TGME49_200290",
]
TOXO_NEGATIVE = [
    "PF3D7_1222600",
    "PF3D7_1031000",
    "PF3D7_0209000",
    "PF3D7_1346700",
    "PF3D7_1346800",
    "PF3D7_0935400",
    "PF3D7_0406200",
    "PF3D7_1408200",
]

# -- FungiDB --
FUNGI_SITE_ID = "fungidb"
FUNGI_TARGET_PARAMS: JSONObject = cast(
    "JSONObject", {"organism": "Aspergillus fumigatus Af293"}
)
FUNGI_POSITIVE = [
    "Afu1g00100",
    "Afu1g00110",
    "Afu1g00120",
    "Afu1g00130",
    "Afu1g00140",
    "Afu1g00150",
    "Afu1g00160",
    "Afu1g00170",
    "Afu1g00180",
    "Afu1g00200",
]
FUNGI_NEGATIVE = [
    "PF3D7_1222600",
    "PF3D7_1031000",
    "PF3D7_0209000",
    "PF3D7_1346700",
    "PF3D7_1346800",
    "PF3D7_0935400",
    "PF3D7_0406200",
    "PF3D7_1408200",
]

# -- TriTrypDB --
TRITRYP_SITE_ID = "tritrypdb"
TRITRYP_TARGET_PARAMS: JSONObject = cast(
    "JSONObject", {"organism": "Trypanosoma brucei brucei TREU927"}
)
TRITRYP_POSITIVE = [
    "Tb05.5K5.10",
    "Tb05.5K5.100",
    "Tb05.5K5.110",
    "Tb05.5K5.120",
    "Tb05.5K5.130",
    "Tb05.5K5.140",
    "Tb05.5K5.150",
    "Tb05.5K5.160",
    "Tb05.5K5.170",
    "Tb05.5K5.180",
]
TRITRYP_NEGATIVE = [
    "PF3D7_1222600",
    "PF3D7_1031000",
    "PF3D7_0209000",
    "PF3D7_1346700",
    "PF3D7_1346800",
    "PF3D7_0935400",
    "PF3D7_0406200",
    "PF3D7_1408200",
]

# -- Large control set (PlasmoDB, 50 genes) --
PLASMO_LARGE_POSITIVE = [
    "PF3D7_0100100",
    "PF3D7_0100200",
    "PF3D7_0100300",
    "PF3D7_0100400",
    "PF3D7_0100500",
    "PF3D7_0100600",
    "PF3D7_0100700",
    "PF3D7_0100800",
    "PF3D7_0100900",
    "PF3D7_0101000",
    "PF3D7_0101100",
    "PF3D7_0101200",
    "PF3D7_0101300",
    "PF3D7_0101400",
    "PF3D7_0101500",
    "PF3D7_0101600",
    "PF3D7_0101700",
    "PF3D7_0101800",
    "PF3D7_0101900",
    "PF3D7_0102000",
    "PF3D7_0102100",
    "PF3D7_0102200",
    "PF3D7_0102300",
    "PF3D7_0102400",
    "PF3D7_0102500",
    "PF3D7_0102600",
    "PF3D7_0102700",
    "PF3D7_0102800",
    "PF3D7_0102900",
    "PF3D7_0103000",
    "PF3D7_1222600",
    "PF3D7_1031000",
    "PF3D7_0209000",
    "PF3D7_1346700",
    "PF3D7_1346800",
    "PF3D7_0935400",
    "PF3D7_0406200",
    "PF3D7_1408200",
    "PF3D7_1216500",
    "PF3D7_1477700",
    "PF3D7_0103100",
    "PF3D7_0103200",
    "PF3D7_0103300",
    "PF3D7_0103400",
    "PF3D7_0103500",
    "PF3D7_0103600",
    "PF3D7_0103700",
    "PF3D7_0103800",
    "PF3D7_0103900",
    "PF3D7_0104000",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def _close_wdk_clients() -> AsyncGenerator[None]:
    """Close shared WDK clients after each test to avoid connection leaks."""
    yield
    try:
        router = get_site_router()
        await router.close_all()
    except RuntimeError, OSError:
        pass  # Client already closed or event loop torn down


# ---------------------------------------------------------------------------
# 1. Positive intersection tests across databases
# ---------------------------------------------------------------------------


class TestIntersectionMultiDb:
    """Test _run_intersection_control with positive controls per database.

    GenesByTaxon returns ALL genes for the target organism. Positive controls
    are known genes from that organism, so ALL should appear in the
    intersection (intersectionCount == len(controls_ids)).
    """

    @pytest.mark.asyncio
    async def test_plasmodb_positive_intersection(self) -> None:
        """All 10 P. falciparum genes should intersect with GenesByTaxon."""
        config = IntersectionConfig(
            site_id=PLASMO_SITE_ID,
            record_type=RECORD_TYPE,
            target_search_name="GenesByTaxon",
            target_parameters=PLASMO_TARGET_PARAMS,
            controls_search_name=CONTROLS_SEARCH_NAME,
            controls_param_name=CONTROLS_PARAM_NAME,
            controls_value_format=CONTROLS_VALUE_FORMAT,
        )
        result = await _run_intersection_control(config, PLASMO_POSITIVE)

        assert result.get("targetStepId") is not None
        assert isinstance(result.get("targetStepId"), int)

        target_count = result.get("targetEstimatedSize")
        assert target_count is not None
        assert isinstance(target_count, (int, float))
        assert int(target_count) > 0

        assert result.get("controlsCount") == len(PLASMO_POSITIVE)

        intersection_count = result.get("intersectionCount")
        assert intersection_count is not None
        assert isinstance(intersection_count, (int, float))
        assert int(intersection_count) == len(PLASMO_POSITIVE), (
            f"Expected all {len(PLASMO_POSITIVE)} positive controls to intersect, "
            f"got {intersection_count}"
        )

    @pytest.mark.asyncio
    async def test_toxodb_positive_intersection(self) -> None:
        """All 10 T. gondii genes should intersect with GenesByTaxon."""
        config = IntersectionConfig(
            site_id=TOXO_SITE_ID,
            record_type=RECORD_TYPE,
            target_search_name="GenesByTaxon",
            target_parameters=TOXO_TARGET_PARAMS,
            controls_search_name=CONTROLS_SEARCH_NAME,
            controls_param_name=CONTROLS_PARAM_NAME,
            controls_value_format=CONTROLS_VALUE_FORMAT,
        )
        result = await _run_intersection_control(config, TOXO_POSITIVE)

        assert result.get("targetStepId") is not None
        assert isinstance(result.get("targetStepId"), int)

        target_count = result.get("targetEstimatedSize")
        assert target_count is not None
        assert isinstance(target_count, (int, float))
        assert int(target_count) > 0

        assert result.get("controlsCount") == len(TOXO_POSITIVE)

        intersection_count = result.get("intersectionCount")
        assert intersection_count is not None
        assert isinstance(intersection_count, (int, float))
        assert int(intersection_count) == len(TOXO_POSITIVE), (
            f"Expected all {len(TOXO_POSITIVE)} positive controls to intersect, "
            f"got {intersection_count}"
        )

    @pytest.mark.asyncio
    async def test_fungidb_positive_intersection(self) -> None:
        """All 10 A. fumigatus genes should intersect with GenesByTaxon."""
        config = IntersectionConfig(
            site_id=FUNGI_SITE_ID,
            record_type=RECORD_TYPE,
            target_search_name="GenesByTaxon",
            target_parameters=FUNGI_TARGET_PARAMS,
            controls_search_name=CONTROLS_SEARCH_NAME,
            controls_param_name=CONTROLS_PARAM_NAME,
            controls_value_format=CONTROLS_VALUE_FORMAT,
        )
        result = await _run_intersection_control(config, FUNGI_POSITIVE)

        assert result.get("targetStepId") is not None
        assert isinstance(result.get("targetStepId"), int)

        target_count = result.get("targetEstimatedSize")
        assert target_count is not None
        assert isinstance(target_count, (int, float))
        assert int(target_count) > 0

        assert result.get("controlsCount") == len(FUNGI_POSITIVE)

        intersection_count = result.get("intersectionCount")
        assert intersection_count is not None
        assert isinstance(intersection_count, (int, float))
        assert int(intersection_count) == len(FUNGI_POSITIVE), (
            f"Expected all {len(FUNGI_POSITIVE)} positive controls to intersect, "
            f"got {intersection_count}"
        )

    @pytest.mark.asyncio
    async def test_tritrypdb_positive_intersection(self) -> None:
        """All 10 T. brucei genes should intersect with GenesByTaxon."""
        config = IntersectionConfig(
            site_id=TRITRYP_SITE_ID,
            record_type=RECORD_TYPE,
            target_search_name="GenesByTaxon",
            target_parameters=TRITRYP_TARGET_PARAMS,
            controls_search_name=CONTROLS_SEARCH_NAME,
            controls_param_name=CONTROLS_PARAM_NAME,
            controls_value_format=CONTROLS_VALUE_FORMAT,
        )
        result = await _run_intersection_control(config, TRITRYP_POSITIVE)

        assert result.get("targetStepId") is not None
        assert isinstance(result.get("targetStepId"), int)

        target_count = result.get("targetEstimatedSize")
        assert target_count is not None
        assert isinstance(target_count, (int, float))
        assert int(target_count) > 0

        assert result.get("controlsCount") == len(TRITRYP_POSITIVE)

        intersection_count = result.get("intersectionCount")
        assert intersection_count is not None
        assert isinstance(intersection_count, (int, float))
        assert int(intersection_count) == len(TRITRYP_POSITIVE), (
            f"Expected all {len(TRITRYP_POSITIVE)} positive controls to intersect, "
            f"got {intersection_count}"
        )


# ---------------------------------------------------------------------------
# 2. Negative intersection tests — cross-species genes should NOT intersect
# ---------------------------------------------------------------------------


class TestNegativeControlsMultiDb:
    """Test that cross-species genes produce zero intersection.

    Negative controls are genes from a DIFFERENT organism than the target.
    GenesByTaxon for organism X should NOT contain genes from organism Y,
    so the intersection should be 0.
    """

    @pytest.mark.asyncio
    async def test_plasmodb_negative_no_intersection(self) -> None:
        """T. gondii genes should NOT appear in P. falciparum GenesByTaxon."""
        config = IntersectionConfig(
            site_id=PLASMO_SITE_ID,
            record_type=RECORD_TYPE,
            target_search_name="GenesByTaxon",
            target_parameters=PLASMO_TARGET_PARAMS,
            controls_search_name=CONTROLS_SEARCH_NAME,
            controls_param_name=CONTROLS_PARAM_NAME,
            controls_value_format=CONTROLS_VALUE_FORMAT,
        )
        result = await _run_intersection_control(config, PLASMO_NEGATIVE)

        assert result.get("targetStepId") is not None
        assert result.get("controlsCount") == len(PLASMO_NEGATIVE)

        intersection_count = result.get("intersectionCount")
        assert intersection_count is not None
        assert isinstance(intersection_count, (int, float))
        assert int(intersection_count) == 0, (
            f"Expected 0 cross-species intersection, got {intersection_count}"
        )

    @pytest.mark.asyncio
    async def test_toxodb_negative_no_intersection(self) -> None:
        """P. falciparum genes should NOT appear in T. gondii GenesByTaxon."""
        config = IntersectionConfig(
            site_id=TOXO_SITE_ID,
            record_type=RECORD_TYPE,
            target_search_name="GenesByTaxon",
            target_parameters=TOXO_TARGET_PARAMS,
            controls_search_name=CONTROLS_SEARCH_NAME,
            controls_param_name=CONTROLS_PARAM_NAME,
            controls_value_format=CONTROLS_VALUE_FORMAT,
        )
        result = await _run_intersection_control(config, TOXO_NEGATIVE)

        assert result.get("targetStepId") is not None
        assert result.get("controlsCount") == len(TOXO_NEGATIVE)

        intersection_count = result.get("intersectionCount")
        assert intersection_count is not None
        assert isinstance(intersection_count, (int, float))
        assert int(intersection_count) == 0, (
            f"Expected 0 cross-species intersection, got {intersection_count}"
        )

    @pytest.mark.asyncio
    async def test_fungidb_negative_no_intersection(self) -> None:
        """P. falciparum genes should NOT appear in A. fumigatus GenesByTaxon."""
        config = IntersectionConfig(
            site_id=FUNGI_SITE_ID,
            record_type=RECORD_TYPE,
            target_search_name="GenesByTaxon",
            target_parameters=FUNGI_TARGET_PARAMS,
            controls_search_name=CONTROLS_SEARCH_NAME,
            controls_param_name=CONTROLS_PARAM_NAME,
            controls_value_format=CONTROLS_VALUE_FORMAT,
        )
        result = await _run_intersection_control(config, FUNGI_NEGATIVE)

        assert result.get("targetStepId") is not None
        assert result.get("controlsCount") == len(FUNGI_NEGATIVE)

        intersection_count = result.get("intersectionCount")
        assert intersection_count is not None
        assert isinstance(intersection_count, (int, float))
        assert int(intersection_count) == 0, (
            f"Expected 0 cross-species intersection, got {intersection_count}"
        )

    @pytest.mark.asyncio
    async def test_tritrypdb_negative_no_intersection(self) -> None:
        """P. falciparum genes should NOT appear in T. brucei GenesByTaxon."""
        config = IntersectionConfig(
            site_id=TRITRYP_SITE_ID,
            record_type=RECORD_TYPE,
            target_search_name="GenesByTaxon",
            target_parameters=TRITRYP_TARGET_PARAMS,
            controls_search_name=CONTROLS_SEARCH_NAME,
            controls_param_name=CONTROLS_PARAM_NAME,
            controls_value_format=CONTROLS_VALUE_FORMAT,
        )
        result = await _run_intersection_control(config, TRITRYP_NEGATIVE)

        assert result.get("targetStepId") is not None
        assert result.get("controlsCount") == len(TRITRYP_NEGATIVE)

        intersection_count = result.get("intersectionCount")
        assert intersection_count is not None
        assert isinstance(intersection_count, (int, float))
        assert int(intersection_count) == 0, (
            f"Expected 0 cross-species intersection, got {intersection_count}"
        )


# ---------------------------------------------------------------------------
# 3. Full positive + negative control flow per database
# ---------------------------------------------------------------------------


class TestFullControlFlowMultiDb:
    """Test run_positive_negative_controls end-to-end per database.

    Each test runs both positive and negative controls in a single call.
    Positive controls (same-organism genes) should yield recall close to 1.0.
    Negative controls (cross-organism genes) should yield FPR == 0.0.
    """

    @pytest.mark.asyncio
    async def test_plasmodb_full_flow(self) -> None:
        """PlasmoDB: positive recall ~1.0, negative FPR == 0.0."""
        config = IntersectionConfig(
            site_id=PLASMO_SITE_ID,
            record_type=RECORD_TYPE,
            target_search_name="GenesByTaxon",
            target_parameters=PLASMO_TARGET_PARAMS,
            controls_search_name=CONTROLS_SEARCH_NAME,
            controls_param_name=CONTROLS_PARAM_NAME,
            controls_value_format=CONTROLS_VALUE_FORMAT,
        )
        result = await run_positive_negative_controls(
            config,
            positive_controls=PLASMO_POSITIVE,
            negative_controls=PLASMO_NEGATIVE,
        )

        _print_full_flow_result("PlasmoDB", result)
        _assert_full_flow(result, PLASMO_SITE_ID, PLASMO_POSITIVE, PLASMO_NEGATIVE)

    @pytest.mark.asyncio
    async def test_toxodb_full_flow(self) -> None:
        """ToxoDB: positive recall ~1.0, negative FPR == 0.0."""
        config = IntersectionConfig(
            site_id=TOXO_SITE_ID,
            record_type=RECORD_TYPE,
            target_search_name="GenesByTaxon",
            target_parameters=TOXO_TARGET_PARAMS,
            controls_search_name=CONTROLS_SEARCH_NAME,
            controls_param_name=CONTROLS_PARAM_NAME,
            controls_value_format=CONTROLS_VALUE_FORMAT,
        )
        result = await run_positive_negative_controls(
            config,
            positive_controls=TOXO_POSITIVE,
            negative_controls=TOXO_NEGATIVE,
        )

        _print_full_flow_result("ToxoDB", result)
        _assert_full_flow(result, TOXO_SITE_ID, TOXO_POSITIVE, TOXO_NEGATIVE)

    @pytest.mark.asyncio
    async def test_fungidb_full_flow(self) -> None:
        """FungiDB: positive recall ~1.0, negative FPR == 0.0."""
        config = IntersectionConfig(
            site_id=FUNGI_SITE_ID,
            record_type=RECORD_TYPE,
            target_search_name="GenesByTaxon",
            target_parameters=FUNGI_TARGET_PARAMS,
            controls_search_name=CONTROLS_SEARCH_NAME,
            controls_param_name=CONTROLS_PARAM_NAME,
            controls_value_format=CONTROLS_VALUE_FORMAT,
        )
        result = await run_positive_negative_controls(
            config,
            positive_controls=FUNGI_POSITIVE,
            negative_controls=FUNGI_NEGATIVE,
        )

        _print_full_flow_result("FungiDB", result)
        _assert_full_flow(result, FUNGI_SITE_ID, FUNGI_POSITIVE, FUNGI_NEGATIVE)

    @pytest.mark.asyncio
    async def test_tritrypdb_full_flow(self) -> None:
        """TriTrypDB: positive recall ~1.0, negative FPR == 0.0."""
        config = IntersectionConfig(
            site_id=TRITRYP_SITE_ID,
            record_type=RECORD_TYPE,
            target_search_name="GenesByTaxon",
            target_parameters=TRITRYP_TARGET_PARAMS,
            controls_search_name=CONTROLS_SEARCH_NAME,
            controls_param_name=CONTROLS_PARAM_NAME,
            controls_value_format=CONTROLS_VALUE_FORMAT,
        )
        result = await run_positive_negative_controls(
            config,
            positive_controls=TRITRYP_POSITIVE,
            negative_controls=TRITRYP_NEGATIVE,
        )

        _print_full_flow_result("TriTrypDB", result)
        _assert_full_flow(result, TRITRYP_SITE_ID, TRITRYP_POSITIVE, TRITRYP_NEGATIVE)


# ---------------------------------------------------------------------------
# 4. Large control set test
# ---------------------------------------------------------------------------


class TestLargeControlSets:
    """Test intersection with a larger set of 50 positive controls.

    All 50 P. falciparum genes should appear in the GenesByTaxon result
    for P. falciparum 3D7. This exercises the code path for larger
    dataset uploads and pagination.
    """

    @pytest.mark.asyncio
    async def test_plasmodb_50_positive_controls(self) -> None:
        """All 50 P. falciparum genes should intersect with GenesByTaxon."""
        assert len(PLASMO_LARGE_POSITIVE) == 50

        config = IntersectionConfig(
            site_id=PLASMO_SITE_ID,
            record_type=RECORD_TYPE,
            target_search_name="GenesByTaxon",
            target_parameters=PLASMO_TARGET_PARAMS,
            controls_search_name=CONTROLS_SEARCH_NAME,
            controls_param_name=CONTROLS_PARAM_NAME,
            controls_value_format=CONTROLS_VALUE_FORMAT,
        )
        result = await _run_intersection_control(config, PLASMO_LARGE_POSITIVE)

        assert result.get("targetStepId") is not None
        assert isinstance(result.get("targetStepId"), int)

        target_count = result.get("targetEstimatedSize")
        assert target_count is not None
        assert isinstance(target_count, (int, float))
        assert int(target_count) > 0

        assert result.get("controlsCount") == 50

        intersection_count = result.get("intersectionCount")
        assert intersection_count is not None
        assert isinstance(intersection_count, (int, float))
        assert int(intersection_count) == 50, (
            f"Expected all 50 positive controls to intersect, got {intersection_count}"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _print_full_flow_result(db_name: str, result: ControlTestResult) -> None:
    """No-op: kept for call-site compatibility."""
    _ = db_name, result


def _assert_full_flow(
    result: ControlTestResult,
    site_id: str,
    positive_controls: list[str],
    negative_controls: list[str],
) -> None:
    """Shared assertions for full control flow tests."""
    assert result.site_id == site_id
    assert result.record_type == RECORD_TYPE

    # Target assertions
    assert result.target.step_id is not None
    assert result.target.estimated_size is not None
    assert result.target.estimated_size > 0

    # Positive control assertions
    assert result.positive is not None, "Positive controls result should not be None"
    assert result.positive.controls_count == len(positive_controls)

    assert result.positive.intersection_count == len(positive_controls), (
        f"Expected recall == 1.0 (all {len(positive_controls)} positives intersect), "
        f"but only {result.positive.intersection_count} did"
    )

    assert result.positive.recall is not None
    assert result.positive.recall == 1.0, (
        f"Expected recall == 1.0, got {result.positive.recall}"
    )

    # Negative control assertions -- second control run must succeed
    # (this was the cascade-delete bug)
    assert result.negative is not None, (
        "Negative controls result should not be None -- "
        "this means the second control run FAILED"
    )
    assert result.negative.controls_count == len(negative_controls)

    assert result.negative.intersection_count == 0, (
        f"Expected 0 cross-species intersection, got {result.negative.intersection_count}"
    )

    assert result.negative.false_positive_rate is not None
    assert result.negative.false_positive_rate == 0.0, (
        f"Expected FPR == 0.0, got {result.negative.false_positive_rate}"
    )

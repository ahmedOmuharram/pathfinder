"""Live integration test against PlasmoDB WDK.

This is the EXACT same query the model runs during optimization:
  - Search: GenesByRNASeqpfal3D7_Su_seven_stages_rnaSeq_RSRC
  - Record type: transcript
  - Positive controls: 10 known P. falciparum gametocyte-upregulated genes
  - Negative controls: 8 known asexual-stage housekeeping genes
  - Controls search: GeneByLocusTag (uses input-dataset parameter)
  - Fixed params: Gametocyte V vs Ring+Troph+Schiz, up-regulated, TPM ≥ 10

Requires network access to plasmodb.org.  Run with:

    pytest src/veupath_chatbot/tests/integration/test_live_control_tests.py -v -s

Skip with:

    pytest -m "not live_wdk"
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import cast

import pytest

from veupath_chatbot.integrations.veupathdb.site_router import get_site_router
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.control_tests import (
    _run_intersection_control,
    run_positive_negative_controls,
)

SITE_ID = "plasmodb"
RECORD_TYPE = "transcript"
TARGET_SEARCH_NAME = "GenesByRNASeqpfal3D7_Su_seven_stages_rnaSeq_RSRC"
CONTROLS_SEARCH_NAME = "GeneByLocusTag"
CONTROLS_PARAM_NAME = "ds_gene_ids"

# Fixed parameters using WDK *term* values (not display values!).
#
# WDK single-pick-vocabulary params have different term vs display names:
#   profileset_generic  term: "P. falciparum Su Seven Stages RNA Seq data -   unstranded"
#                    display: "Transcriptomes of 7 sexual and asexual life stages  unstranded"
#   min_max_avg_comp    term: "average1"   display: "average"
#   min_max_avg_ref     term: "average1"   display: "average"
#   protein_coding_only term: "yes"        display: "protein coding"
#   hard_floor          term: "5271.566971799924622138383777958655190582"  display: "10 reads"
#
# samples_fc_ref_generic and samples_fc_comp_generic have term == display.
FIXED_PARAMETERS = {
    "dataset_url": "https://PlasmoDB.org/a/app/record/dataset/DS_66f9e70b8a",
    "profileset_generic": "P. falciparum Su Seven Stages RNA Seq data -   unstranded",
    "regulated_dir": "up-regulated",
    "samples_fc_comp_generic": ["Gametocyte V"],
    "min_max_avg_comp": "average1",
    "samples_fc_ref_generic": [
        "Ring",
        "Early Trophozoite",
        "Late Trophozoite",
        "Schizont",
    ],
    "min_max_avg_ref": "average1",
    "hard_floor": "5271.566971799924622138383777958655190582",
    "protein_coding_only": "yes",
}

# Known gametocyte-upregulated genes (positive controls)
POSITIVE_CONTROLS = [
    "PF3D7_1222600",  # PfAP2-G – master regulator of sexual commitment
    "PF3D7_1031000",  # Pfs25 – surface antigen, TBV candidate
    "PF3D7_0209000",  # Pfs230 – gamete fertility factor
    "PF3D7_1346700",  # Pfs48/45 – TBV candidate
    "PF3D7_1346800",  # Pfs47 – female gamete fertility
    "PF3D7_0935400",  # CDPK4 – male gametocyte kinase
    "PF3D7_0406200",  # MDV1/PEG3 – male gametocyte development
    "PF3D7_1408200",  # Pf11-1 – gametocyte-specific
    "PF3D7_1216500",  # GEP1 – gametocyte egress protein
    "PF3D7_1477700",  # HAP2/GCS1 – male gamete fusion factor
]

# Known asexual-stage housekeeping genes (negative controls)
NEGATIVE_CONTROLS = [
    "PF3D7_1462800",  # GAPDH
    "PF3D7_1246200",  # Actin I
    "PF3D7_0422300",  # α-Tubulin
    "PF3D7_0317600",  # Histone H2B
    "PF3D7_1357000",  # EF-1α
    "PF3D7_0708400",  # HSP90
    "PF3D7_0818900",  # HSP70-1
    "PF3D7_0617800",  # Histone H3
]

# A moderate fold_change that should capture several gametocyte genes
TEST_FOLD_CHANGE = "2"


@pytest.fixture(autouse=True)
async def _close_wdk_clients() -> AsyncGenerator[None]:
    """Close shared WDK clients after each test.

    The site_router caches httpx clients.  If we don't close them between
    tests, the second test tries to reuse connections from an event loop
    that asyncio has already torn down → ``RuntimeError: Event loop is
    closed``.
    """
    yield
    try:
        router = get_site_router()
        await router.close_all()
    except Exception:
        pass


pytestmark = pytest.mark.live_wdk


class TestLiveSingleIntersection:
    """Test _run_intersection_control against live PlasmoDB.

    This exercises the EXACT code path that was failing:
    - Creates a target step (RNA-Seq search)
    - Creates a controls step (GeneByLocusTag via dataset upload)
    - Creates a combined step (INTERSECT)
    - Creates a temporary strategy (required by WDK to run reports)
    - Queries intersection count + record IDs
    - Cleans up (deletes strategy)


    """

    @pytest.mark.asyncio
    async def test_positive_controls_intersection(self) -> None:
        """Intersect RNA-Seq results with positive controls.

        With fold_change=2 we expect several known gametocyte genes to appear.
        """
        target_params = cast(
            JSONObject, {**FIXED_PARAMETERS, "fold_change": TEST_FOLD_CHANGE}
        )

        result = await _run_intersection_control(
            site_id=SITE_ID,
            record_type=RECORD_TYPE,
            target_search_name=TARGET_SEARCH_NAME,
            target_parameters=target_params,
            controls_search_name=CONTROLS_SEARCH_NAME,
            controls_param_name=CONTROLS_PARAM_NAME,
            controls_ids=POSITIVE_CONTROLS,
            controls_value_format="newline",
            controls_extra_parameters=None,
        )

        print("\n=== Positive controls result ===")
        print(f"  targetStepId:       {result.get('targetStepId')}")
        print(f"  targetResultCount:  {result.get('targetResultCount')}")
        print(f"  controlsCount:      {result.get('controlsCount')}")
        print(f"  intersectionCount:  {result.get('intersectionCount')}")
        print(f"  intersectionIds:    {result.get('intersectionIds')}")

        # Basic sanity: target step was created
        target_step_id = result.get("targetStepId")
        assert target_step_id is not None
        assert isinstance(target_step_id, int)

        # Target result count should be a positive integer (hundreds or thousands
        # of genes pass fold_change >= 2 for gametocyte V vs asexual)
        target_result_count = result.get("targetResultCount")
        assert target_result_count is not None
        assert isinstance(target_result_count, (int, float))
        assert int(target_result_count) > 0

        # Intersection count should be a non-negative integer
        intersection_count = result.get("intersectionCount")
        assert intersection_count is not None
        assert isinstance(intersection_count, (int, float))
        assert int(intersection_count) >= 0

        # With fold_change=2, we should find at least some gametocyte markers
        assert result.get("controlsCount") == len(POSITIVE_CONTROLS)
        assert int(intersection_count) > 0, (
            "Expected at least some positive controls to appear at fold_change=2"
        )

    @pytest.mark.asyncio
    async def test_negative_controls_intersection(self) -> None:
        """Intersect RNA-Seq results with negative controls.

        Housekeeping genes should show low overlap with gametocyte-upregulated.
        """
        target_params = cast(
            JSONObject, {**FIXED_PARAMETERS, "fold_change": TEST_FOLD_CHANGE}
        )

        result = await _run_intersection_control(
            site_id=SITE_ID,
            record_type=RECORD_TYPE,
            target_search_name=TARGET_SEARCH_NAME,
            target_parameters=target_params,
            controls_search_name=CONTROLS_SEARCH_NAME,
            controls_param_name=CONTROLS_PARAM_NAME,
            controls_ids=NEGATIVE_CONTROLS,
            controls_value_format="newline",
            controls_extra_parameters=None,
        )

        print("\n=== Negative controls result ===")
        print(f"  targetStepId:       {result.get('targetStepId')}")
        print(f"  targetResultCount:  {result.get('targetResultCount')}")
        print(f"  controlsCount:      {result.get('controlsCount')}")
        print(f"  intersectionCount:  {result.get('intersectionCount')}")
        print(f"  intersectionIds:    {result.get('intersectionIds')}")

        target_step_id = result.get("targetStepId")
        assert target_step_id is not None
        target_result_count = result.get("targetResultCount")
        assert target_result_count is not None
        assert isinstance(target_result_count, (int, float))
        assert int(target_result_count) > 0
        assert result.get("controlsCount") == len(NEGATIVE_CONTROLS)
        assert result.get("intersectionCount") is not None


class TestLiveFullControlFlow:
    """Test run_positive_negative_controls end-to-end against live PlasmoDB.

    This is the EXACT function that the parameter optimizer calls on every
    trial.  It must succeed with BOTH positive AND negative controls in a
    single invocation.  This was the bug: the second control set failed
    because WDK cascade-deleted the target step when the first strategy
    was cleaned up.


    """

    @pytest.mark.asyncio
    async def test_positive_and_negative_together(self) -> None:
        """Run both positive + negative controls in one call.

        This is the exact call that was failing with
        "437577363 is not a valid step ID" on every trial.
        """
        target_params = cast(
            JSONObject, {**FIXED_PARAMETERS, "fold_change": TEST_FOLD_CHANGE}
        )

        result = await run_positive_negative_controls(
            site_id=SITE_ID,
            record_type=RECORD_TYPE,
            target_search_name=TARGET_SEARCH_NAME,
            target_parameters=target_params,
            controls_search_name=CONTROLS_SEARCH_NAME,
            controls_param_name=CONTROLS_PARAM_NAME,
            positive_controls=POSITIVE_CONTROLS,
            negative_controls=NEGATIVE_CONTROLS,
            controls_value_format="newline",
        )

        print("\n=== Full positive + negative controls result ===")
        print(f"  siteId:     {result.get('siteId')}")
        print(f"  recordType: {result.get('recordType')}")
        target_raw = result.get("target") or {}
        target = target_raw if isinstance(target_raw, dict) else {}
        print(f"  target.stepId:      {target.get('stepId')}")
        print(f"  target.resultCount: {target.get('resultCount')}")

        pos_raw = result.get("positive")
        pos = pos_raw if isinstance(pos_raw, dict) else None
        if pos:
            print(f"  positive.controlsCount:      {pos.get('controlsCount')}")
            print(f"  positive.intersectionCount:  {pos.get('intersectionCount')}")
            print(f"  positive.recall:             {pos.get('recall')}")
            print(f"  positive.intersectionIds:    {pos.get('intersectionIds')}")
            print(f"  positive.missingIdsSample:   {pos.get('missingIdsSample')}")

        neg_raw = result.get("negative")
        neg = neg_raw if isinstance(neg_raw, dict) else None
        if neg:
            print(f"  negative.controlsCount:      {neg.get('controlsCount')}")
            print(f"  negative.intersectionCount:  {neg.get('intersectionCount')}")
            print(f"  negative.falsePositiveRate:  {neg.get('falsePositiveRate')}")
            print(f"  negative.intersectionIds:    {neg.get('intersectionIds')}")
            print(f"  negative.unexpectedHitsSample: {neg.get('unexpectedHitsSample')}")

        assert result.get("siteId") == SITE_ID
        assert result.get("recordType") == RECORD_TYPE
        assert target.get("stepId") is not None
        result_count = target.get("resultCount")
        assert result_count is not None
        assert isinstance(result_count, (int, float))
        assert int(result_count) > 0

        assert pos is not None, "Positive controls result should not be None"
        assert pos.get("controlsCount") == len(POSITIVE_CONTROLS)
        pos_ic = pos.get("intersectionCount")
        assert pos_ic is not None
        assert isinstance(pos_ic, (int, float))
        assert int(pos_ic) > 0, (
            "Expected at least some positive controls at fold_change=2"
        )
        pos_recall = pos.get("recall")
        assert pos_recall is not None
        assert isinstance(pos_recall, (int, float))
        assert float(pos_recall) > 0

        # THIS is the part that was failing before the fix.
        # If the cascade-delete bug still exists, this will blow up with
        # "X is not a valid step ID" from WDK.
        assert neg is not None, (
            "Negative controls result should not be None – "
            "this means the second control run FAILED"
        )
        assert neg.get("controlsCount") == len(NEGATIVE_CONTROLS)
        assert neg.get("intersectionCount") is not None
        # Housekeeping genes *shouldn't* be gametocyte-upregulated, but at
        # a low fold_change some might sneak through.  We just check it ran.
        assert neg.get("falsePositiveRate") is not None

        neg_fpr = neg.get("falsePositiveRate")
        if (
            pos_recall is not None
            and neg_fpr is not None
            and isinstance(neg_fpr, (int, float))
        ):
            print(
                f"\n  recall={float(pos_recall):.3f}  "
                f"FPR={float(neg_fpr):.3f}  "
                f"→ {'GOOD' if float(pos_recall) > float(neg_fpr) else 'BAD'}"
            )

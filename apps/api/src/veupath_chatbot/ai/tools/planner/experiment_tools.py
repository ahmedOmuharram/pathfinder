"""Planner-mode tools for running control tests.

Provides :class:`ExperimentToolsMixin` with the ``run_control_tests`` tool.
"""

from typing import Annotated, cast

from kani import AIParam, ai_function

from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.control_tests import (
    IntersectionConfig,
    run_positive_negative_controls,
)
from veupath_chatbot.services.export import get_export_service
from veupath_chatbot.services.gene_sets.operations import fetch_gene_ids_from_step

logger = get_logger(__name__)


async def _run_step_control_tests(
    *,
    site_id: str,
    wdk_step_id: int,
    positive_controls: list[str] | None,
    negative_controls: list[str] | None,
) -> JSONObject:
    """Run control tests against an existing WDK step using Python set ops.

    Fetches the step's gene IDs, then computes intersection with controls.
    No temporary WDK strategy needed.
    """
    api = get_strategy_api(site_id)
    gene_ids = await fetch_gene_ids_from_step(api, step_id=wdk_step_id)
    result_set = set(gene_ids)

    result: JSONObject = {
        "siteId": site_id,
        "wdkStepId": wdk_step_id,
        "resultCount": len(result_set),
        "positive": None,
        "negative": None,
    }

    pos = [s.strip() for s in (positive_controls or []) if s.strip()]
    neg = [s.strip() for s in (negative_controls or []) if s.strip()]

    if pos:
        pos_set = set(pos)
        found = pos_set & result_set
        missing = sorted(pos_set - result_set)
        result["positive"] = cast(
            "JSONValue",
            {
                "controlsCount": len(pos),
                "intersectionCount": len(found),
                "intersectionIds": sorted(found),
                "missingIds": missing,
                "recall": len(found) / len(pos) if pos else None,
            },
        )

    if neg:
        neg_set = set(neg)
        false_positives = neg_set & result_set
        result["negative"] = cast(
            "JSONValue",
            {
                "controlsCount": len(neg),
                "intersectionCount": len(false_positives),
                "intersectionIds": sorted(false_positives),
                "falsePositiveRate": len(false_positives) / len(neg) if neg else None,
            },
        )

    return result


class ExperimentToolsMixin:
    """Kani tool mixin for experiment control tests."""

    site_id: str = ""

    async def _export_control_result(
        self,
        result: JSONObject,
        name: str,
    ) -> JSONObject:
        """Auto-attach download links to a control test result."""
        try:
            svc = get_export_service()
            json_export = await svc.export_json(result, name)
            result["downloads"] = {
                "json": json_export.url,
                "expiresInSeconds": json_export.expires_in_seconds,
            }
        except (OSError, ValueError, TypeError, KeyError) as e:
            logger.warning("Control test export failed", error=str(e))
        return result

    @ai_function()
    async def run_control_tests_on_step(
        self,
        wdk_step_id: Annotated[
            int,
            AIParam(
                desc=(
                    "WDK step ID from a built strategy to test against. "
                    "Get the step ID from list_current_steps (wdkStepId field on the root step)."
                )
            ),
        ],
        positive_controls: Annotated[
            list[str] | None, AIParam(desc="Known-positive IDs that should be returned")
        ] = None,
        negative_controls: Annotated[
            list[str] | None,
            AIParam(desc="Known-negative IDs that should NOT be returned"),
        ] = None,
    ) -> JSONObject:
        """Run control tests against an already-built WDK strategy step.

        Tests directly against the strategy's actual results using Python set
        operations — no temporary WDK strategy needed.  Use this after building
        a multi-step strategy with ``build_step`` / ``combine_steps``.

        For testing a standalone (not-yet-built) search, use
        ``run_control_tests_on_search`` instead.
        """
        has_positives = positive_controls and len(positive_controls) > 0
        has_negatives = negative_controls and len(negative_controls) > 0
        if not has_positives and not has_negatives:
            return cast(
                "JSONObject",
                {
                    "ok": False,
                    "error": "At least one of positive_controls or negative_controls must be provided.",
                },
            )
        result = await _run_step_control_tests(
            site_id=self.site_id,
            wdk_step_id=wdk_step_id,
            positive_controls=positive_controls,
            negative_controls=negative_controls,
        )
        return await self._export_control_result(
            result, f"step_{wdk_step_id}_control_tests"
        )

    @ai_function()
    async def run_control_tests_on_search(
        self,
        record_type: Annotated[
            str, AIParam(desc="WDK record type (e.g. 'transcript')")
        ],
        target_search_name: Annotated[
            str, AIParam(desc="WDK search/question urlSegment to test")
        ],
        target_parameters: Annotated[
            JSONObject, AIParam(desc="Target search parameter mapping")
        ],
        positive_controls: Annotated[
            list[str] | None, AIParam(desc="Known-positive IDs that should be returned")
        ] = None,
        negative_controls: Annotated[
            list[str] | None,
            AIParam(desc="Known-negative IDs that should NOT be returned"),
        ] = None,
    ) -> JSONObject:
        """Run control tests against a standalone WDK search (not a built strategy).

        Creates a temporary WDK strategy to intersect the search results with
        control gene IDs.  Use ``run_control_tests_on_step`` instead when you
        already have a built multi-step strategy.

        Controls are matched via ``GeneByLocusTag`` (parameter ``ds_gene_ids``).
        For sites that require different matching parameters, build an
        ``IntersectionConfig`` and call ``run_positive_negative_controls``
        from service code directly.
        """
        has_positives = positive_controls and len(positive_controls) > 0
        has_negatives = negative_controls and len(negative_controls) > 0
        if not has_positives and not has_negatives:
            return cast(
                "JSONObject",
                {
                    "ok": False,
                    "error": "At least one of positive_controls or negative_controls must be provided.",
                },
            )
        _cfg = IntersectionConfig(
            site_id=self.site_id,
            record_type=record_type,
            target_search_name=target_search_name,
            target_parameters=target_parameters,
            controls_search_name="GeneByLocusTag",
            controls_param_name="ds_gene_ids",
            controls_value_format="newline",
        )
        result = await run_positive_negative_controls(
            _cfg,
            positive_controls=positive_controls,
            negative_controls=negative_controls,
        )
        return await self._export_control_result(
            result, f"{target_search_name}_control_tests"
        )

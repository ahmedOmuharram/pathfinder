"""Planner-mode tools for running control tests.

Provides :class:`ExperimentToolsMixin` with the ``run_control_tests`` tool.
"""

from typing import Annotated, cast

from kani import AIParam, ai_function

from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.control_tests import run_positive_negative_controls
from veupath_chatbot.services.experiment.types import ControlValueFormat
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

    @ai_function()
    async def run_control_tests(
        self,
        record_type: Annotated[
            str, AIParam(desc="WDK record type (e.g. 'transcript')")
        ],
        target_search_name: Annotated[
            str | None,
            AIParam(
                desc=(
                    "WDK search/question urlSegment. Required when testing a standalone search. "
                    "Omit when using wdk_step_id to test against an existing built step."
                )
            ),
        ] = None,
        target_parameters: Annotated[
            JSONObject | None,
            AIParam(
                desc="Target search parameter mapping (omit when using wdk_step_id)"
            ),
        ] = None,
        wdk_step_id: Annotated[
            int | None,
            AIParam(
                desc=(
                    "WDK step ID from a built strategy to test against. "
                    "Use this to test the actual multi-step strategy results "
                    "instead of a standalone search. Get the step ID from "
                    "list_current_steps (wdkStepId field on the root step)."
                )
            ),
        ] = None,
        controls_search_name: Annotated[
            str,
            AIParam(
                desc=(
                    "Search name that can take a list of record IDs (for positive/negative controls)."
                )
            ),
        ] = "GeneByLocusTag",
        controls_param_name: Annotated[
            str,
            AIParam(desc="Parameter name within controls_search_name that accepts IDs"),
        ] = "ds_gene_ids",
        positive_controls: Annotated[
            list[str] | None, AIParam(desc="Known-positive IDs that should be returned")
        ] = None,
        negative_controls: Annotated[
            list[str] | None,
            AIParam(desc="Known-negative IDs that should NOT be returned"),
        ] = None,
        *,
        controls_value_format: Annotated[
            ControlValueFormat,
            AIParam(desc="How to encode ID list for the controls parameter"),
        ] = "newline",
        controls_extra_parameters: Annotated[
            JSONObject | None,
            AIParam(desc="Extra fixed parameters for the controls search"),
        ] = None,
        id_field: Annotated[
            str | None,
            AIParam(
                desc=(
                    "Optional record-id field name to extract from answer records "
                    "(varies by site/record type)."
                )
            ),
        ] = None,
    ) -> JSONObject:
        """Run control tests against a WDK search OR a built strategy step.

        Two modes: (1) **Standalone search** — provide ``target_search_name`` +
        ``target_parameters``; creates a temporary WDK strategy to intersect.
        (2) **Built step** — provide ``wdk_step_id`` from ``list_current_steps``;
        tests directly against the strategy's actual results (recommended after
        building a multi-step strategy).
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

        # Mode 2: test against existing built step
        if wdk_step_id is not None:
            result = await _run_step_control_tests(
                site_id=self.site_id,
                wdk_step_id=wdk_step_id,
                positive_controls=positive_controls,
                negative_controls=negative_controls,
            )
        elif target_search_name:
            # Mode 1: standalone search
            result = await run_positive_negative_controls(
                site_id=self.site_id,
                record_type=record_type,
                target_search_name=target_search_name,
                target_parameters=target_parameters or {},
                controls_search_name=controls_search_name,
                controls_param_name=controls_param_name,
                positive_controls=positive_controls,
                negative_controls=negative_controls,
                controls_value_format=controls_value_format,
                controls_extra_parameters=controls_extra_parameters,
                id_field=id_field,
            )
        else:
            return cast(
                "JSONObject",
                {
                    "ok": False,
                    "error": "Provide either wdk_step_id (to test a built strategy) or target_search_name + target_parameters (to test a standalone search).",
                },
            )

        # Auto-generate exports.
        try:
            svc = get_export_service()
            name = f"{target_search_name or 'step'}_control_tests"
            json_export = await svc.export_json(result, name)
            result["downloads"] = {
                "json": json_export.url,
                "expiresInSeconds": json_export.expires_in_seconds,
            }
        except (OSError, ValueError, TypeError, KeyError) as e:
            logger.warning("Control test export failed", error=str(e))

        return result

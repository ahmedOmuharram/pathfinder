"""Planner-mode tools for running control tests.

Provides :class:`ExperimentToolsMixin` with the ``run_control_tests`` tool.
"""

from __future__ import annotations

from typing import Annotated

from kani import AIParam, ai_function

from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.control_tests import run_positive_negative_controls
from veupath_chatbot.services.experiment.types import ControlValueFormat


class ExperimentToolsMixin:
    """Kani tool mixin for experiment control tests."""

    site_id: str

    @ai_function()
    async def run_control_tests(
        self,
        record_type: Annotated[str, AIParam(desc="WDK record type (e.g. 'gene')")],
        target_search_name: Annotated[
            str, AIParam(desc="WDK search/question urlSegment")
        ],
        target_parameters: Annotated[
            JSONObject, AIParam(desc="Target search parameter mapping")
        ],
        controls_search_name: Annotated[
            str,
            AIParam(
                desc=(
                    "Search name that can take a list of record IDs (for positive/negative controls)."
                )
            ),
        ],
        controls_param_name: Annotated[
            str,
            AIParam(desc="Parameter name within controls_search_name that accepts IDs"),
        ],
        positive_controls: Annotated[
            list[str] | None, AIParam(desc="Known-positive IDs that should be returned")
        ] = None,
        negative_controls: Annotated[
            list[str] | None,
            AIParam(desc="Known-negative IDs that should NOT be returned"),
        ] = None,
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
        """Run positive and negative control tests using live WDK (temporary internal strategy)."""
        return await run_positive_negative_controls(
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

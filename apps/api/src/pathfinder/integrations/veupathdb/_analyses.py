"""Analysis, step-filter, and report endpoint methods for VEuPathDBClient."""

from pydantic import JsonValue, TypeAdapter

from pathfinder.integrations.veupathdb._helpers import _validate_list
from pathfinder.integrations.veupathdb.analysis_result import WDKAnalysisNotReadyError
from pathfinder.integrations.veupathdb.wdk_models import (
    WDKAnalysisStatus,
    WDKAnalysisStatusResponse,
    WDKFilterValue,
    WDKStep,
    WDKStepAnalysisConfig,
    WDKStepAnalysisType,
    WDKStepAnalysisTypeResponse,
)
from pathfinder.platform.errors import validate_response
from pathfinder.platform.logging import get_logger
from pathfinder.platform.types import JSONObject

logger = get_logger(__name__)

_ANALYSIS_TYPE_ADAPTER: TypeAdapter[WDKStepAnalysisType] = TypeAdapter(
    WDKStepAnalysisType
)
_ANALYSIS_CONFIG_ADAPTER: TypeAdapter[WDKStepAnalysisConfig] = TypeAdapter(
    WDKStepAnalysisConfig
)


class AnalysisEndpoints:
    """Mixin providing analysis, step-filter, and report WDK endpoints.

    Must be composed with :class:`HTTPClient` which supplies
    ``get``, ``post``, and ``put`` methods.
    """

    async def get(self, path: str, params: JSONObject | None = None) -> JsonValue:
        """Provided by HTTPClient at runtime."""
        raise NotImplementedError  # pragma: no cover

    async def post(
        self,
        path: str,
        json: object = None,
        params: JSONObject | None = None,
    ) -> JsonValue:
        """Provided by HTTPClient at runtime."""
        raise NotImplementedError  # pragma: no cover

    async def put(self, path: str, json: object = None) -> JsonValue:
        """Provided by HTTPClient at runtime."""
        raise NotImplementedError  # pragma: no cover

    # --- Step filters ---

    async def get_step_view_filters(
        self, user_id: str, step_id: int
    ) -> list[WDKFilterValue]:
        """Get filters from a step's searchConfig.

        WDK stores filters as ``searchConfig.filters`` on the step resource.
        The ``viewFilters`` field is read-only in the WDK REST API schema.
        """
        raw = await self.get(f"/users/{user_id}/steps/{step_id}")
        step = WDKStep.model_validate(raw)
        return list(step.search_config.filters)

    async def update_step_view_filters(
        self, user_id: str, step_id: int, filters: list[WDKFilterValue]
    ) -> JsonValue:
        """Update a step's filters through the search-config endpoint.

        The ``filters`` array in the search-config PUT body is the only public
        way to set filter specifications on a step.
        """
        raw = await self.get(f"/users/{user_id}/steps/{step_id}")
        step = WDKStep.model_validate(raw)
        return await self.put(
            f"/users/{user_id}/steps/{step_id}/search-config",
            json={
                "parameters": step.search_config.parameters,
                "filters": [f.model_dump(by_alias=True) for f in filters],
                "wdkWeight": step.search_config.wdk_weight,
            },
        )

    # --- Analysis types ---

    async def list_analysis_types(
        self, user_id: str, step_id: int
    ) -> list[WDKStepAnalysisType]:
        """List available analysis types for a step."""
        raw = await self.get(f"/users/{user_id}/steps/{step_id}/analysis-types")
        return _validate_list(raw, _ANALYSIS_TYPE_ADAPTER)

    async def get_analysis_type(
        self, user_id: str, step_id: int, analysis_type: str
    ) -> WDKStepAnalysisTypeResponse:
        """Get analysis form metadata for a specific analysis type.

        The WDK endpoint returns a ``{searchData, validation}`` envelope
        (same pattern as ``GET .../searches/{name}``).
        """
        raw = await self.get(
            f"/users/{user_id}/steps/{step_id}/analysis-types/{analysis_type}"
        )
        return validate_response(
            WDKStepAnalysisTypeResponse,
            raw,
            f"WDK analysis type response for {analysis_type}",
        )

    # --- Analysis instances ---

    async def list_step_analyses(
        self, user_id: str, step_id: int
    ) -> list[WDKStepAnalysisConfig]:
        """List analyses that have been run on a step."""
        raw = await self.get(f"/users/{user_id}/steps/{step_id}/analyses")
        return _validate_list(raw, _ANALYSIS_CONFIG_ADAPTER)

    async def create_step_analysis(
        self, user_id: str, step_id: int, payload: JSONObject
    ) -> WDKStepAnalysisConfig:
        """Create a new analysis instance for a step."""
        raw = await self.post(
            f"/users/{user_id}/steps/{step_id}/analyses", json=payload
        )
        return validate_response(
            WDKStepAnalysisConfig, raw, "WDK create analysis response"
        )

    async def run_analysis_instance(
        self, user_id: str, step_id: int, analysis_id: int
    ) -> None:
        """Kick off execution of a step analysis instance.

        Return value is unused — callers poll status separately.
        """
        await self.post(
            f"/users/{user_id}/steps/{step_id}/analyses/{analysis_id}/result"
        )

    async def get_analysis_status(
        self, user_id: str, step_id: int, analysis_id: int
    ) -> WDKAnalysisStatus:
        """Poll execution status of a step analysis instance.

        ``GET .../analyses/{analysisId}/result/status`` returns
        ``{"status": "RUNNING"|"COMPLETE"|"ERROR"|...}``.
        Extracts and returns the typed ``WDKAnalysisStatus`` directly.
        """
        raw = await self.get(
            f"/users/{user_id}/steps/{step_id}/analyses/{analysis_id}/result/status"
        )
        return WDKAnalysisStatusResponse.model_validate(raw).status

    async def get_analysis_result(
        self, user_id: str, step_id: int, analysis_id: int
    ) -> JSONObject:
        """Get the result of a completed step analysis instance.

        WDK answers 204 with an empty body while no result exists, which is
        not an empty result.
        """
        raw = await self.get(
            f"/users/{user_id}/steps/{step_id}/analyses/{analysis_id}/result"
        )
        if isinstance(raw, dict):
            return raw
        raise WDKAnalysisNotReadyError(step_id, analysis_id)

    # --- Reports ---

    async def run_step_report(
        self,
        user_id: str,
        step_id: int,
        report_name: str,
        payload: JSONObject | None = None,
    ) -> JsonValue:
        """Run a report on a step."""
        return await self.post(
            f"/users/{user_id}/steps/{step_id}/reports/{report_name}",
            json=payload or {},
        )

"""Search and record-type endpoint methods for VEuPathDBClient."""

import pydantic
from pydantic import TypeAdapter

from pathfinder.integrations.veupathdb.wdk_models import (
    WDKAnswer,
    WDKRecordType,
    WDKSearch,
    WDKSearchConfig,
    WDKSearchResponse,
)
from pathfinder.integrations.veupathdb.wdk_parameters import WDKParameter
from pathfinder.platform.errors import validate_response
from pathfinder.platform.logging import get_logger
from pathfinder.platform.types import JSONObject, JSONValue

logger = get_logger(__name__)


class SearchEndpoints:
    """Mixin providing search and record-type WDK endpoints.

    Must be composed with :class:`HTTPClient` which supplies
    ``get`` and ``post`` methods.
    """

    async def get(self, path: str, params: JSONObject | None = None) -> JSONValue:
        """Provided by HTTPClient at runtime."""
        raise NotImplementedError  # pragma: no cover

    async def post(
        self,
        path: str,
        json: object = None,
        params: JSONObject | None = None,
    ) -> JSONValue:
        """Provided by HTTPClient at runtime."""
        raise NotImplementedError  # pragma: no cover

    async def get_record_types(self, *, expanded: bool = False) -> list[WDKRecordType]:
        """Get available record types.

        Non-expanded responses return plain strings (``["gene", "transcript"]``),
        which are parsed into ``WDKRecordType(url_segment=name)``.  Expanded
        responses return full JSON objects that are validated against the model.
        Items that fail validation are silently skipped.
        """
        params: JSONObject | None = {"format": "expanded"} if expanded else None
        raw = await self.get("/record-types", params=params)
        if not isinstance(raw, list):
            return []
        result: list[WDKRecordType] = []
        for item in raw:
            if isinstance(item, str):
                result.append(WDKRecordType(url_segment=item, display_name=item))
            elif isinstance(item, dict):
                try:
                    result.append(WDKRecordType.model_validate(item))
                except pydantic.ValidationError:
                    logger.warning(
                        "Skipping unparseable record type entry",
                        error_keys=list(item.keys())[:5],
                    )
        return result

    async def get_searches(self, record_type: str) -> list[WDKSearch]:
        """Get searches for a record type."""
        raw = await self.get(f"/record-types/{record_type}/searches")
        if not isinstance(raw, list):
            return []
        result: list[WDKSearch] = []
        for item in raw:
            if isinstance(item, dict):
                try:
                    result.append(WDKSearch.model_validate(item))
                except pydantic.ValidationError:
                    logger.warning(
                        "Skipping unparseable search entry",
                        record_type=record_type,
                        error_keys=list(item.keys())[:5],
                    )
        return result

    async def get_search_details(
        self,
        record_type: str,
        search_name: str,
        *,
        expand_params: bool = True,
    ) -> WDKSearchResponse:
        """Get detailed search configuration including parameters."""
        params: JSONObject | None = {"expandParams": "true"} if expand_params else None
        raw = await self.get(
            f"/record-types/{record_type}/searches/{search_name}",
            params=params,
        )
        return validate_response(
            WDKSearchResponse,
            raw,
            f"WDK search response for {record_type}/{search_name}",
        )

    async def get_search_details_with_params(
        self,
        record_type: str,
        search_name: str,
        context: dict[str, str],
        *,
        expand_params: bool = True,
    ) -> WDKSearchResponse:
        """Get detailed search configuration using provided parameters.

        :param context: WDK-encoded parameter values (all values must be strings).
            Use :func:`encode_wdk_params` to encode non-string
            values before calling.
        """
        params: JSONObject | None = {"expandParams": "true"} if expand_params else None
        raw = await self.post(
            f"/record-types/{record_type}/searches/{search_name}",
            json={"contextParamValues": context},
            params=params,
        )
        return validate_response(
            WDKSearchResponse,
            raw,
            f"WDK search response for {record_type}/{search_name}",
        )

    async def get_refreshed_dependent_params(
        self,
        record_type: str,
        search_name: str,
        param_name: str,
        context: dict[str, str],
    ) -> list[WDKParameter]:
        """Refresh dependent params using WDK's refreshed-dependent-params endpoint.

        :param context: WDK-encoded parameter values (all values must be strings).
            Use :func:`encode_wdk_params` to encode non-string
            values before calling.
        """
        raw = await self.post(
            f"/record-types/{record_type}/searches/{search_name}/refreshed-dependent-params",
            json={
                "changedParam": {
                    "name": param_name,
                    "value": context.get(param_name, ""),
                },
                "contextParamValues": context,
            },
        )
        if not isinstance(raw, list):
            return []
        adapter: TypeAdapter[WDKParameter] = TypeAdapter(WDKParameter)
        result: list[WDKParameter] = []
        for item in raw:
            if isinstance(item, dict):
                try:
                    result.append(adapter.validate_python(item))
                except pydantic.ValidationError:
                    logger.warning(
                        "Skipping unparseable parameter in refreshed-dependent-params",
                        param_keys=list(item.keys())[:5],
                    )
        return result

    async def run_search_report(
        self,
        record_type: str,
        search_name: str,
        search_config: WDKSearchConfig,
        report_config: JSONObject | None = None,
    ) -> WDKAnswer:
        """Run a report on a search without creating a step or strategy.

        Uses WDK's anonymous report endpoint:
        ``POST /record-types/{recordType}/searches/{searchName}/reports/standard``

        This is significantly faster than creating steps/strategies because it
        requires no user session and can be parallelized.

        :param record_type: WDK record type (e.g. ``"transcript"``).
        :param search_name: WDK search name (e.g. ``"GenesByTaxon"``).
        :param search_config: Typed search config (parameters, filters, weight).
        :param report_config: Report config (pagination, attributes, etc.).
        :returns: Parsed ``WDKAnswer`` with typed ``meta`` and ``records``.
        """
        payload: JSONObject = {
            "searchConfig": search_config.model_dump(
                by_alias=True, exclude_defaults=True
            ),
            "reportConfig": report_config or {},
        }
        result = await self.post(
            f"/record-types/{record_type}/searches/{search_name}/reports/standard",
            json=payload,
        )
        return validate_response(
            WDKAnswer, result, f"WDK answer for {record_type}/{search_name}"
        )

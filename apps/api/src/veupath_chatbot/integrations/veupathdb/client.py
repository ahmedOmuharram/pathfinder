"""HTTP client for VEuPathDB WDK REST API with retries and cookies."""

import asyncio
import json
from collections.abc import Mapping, Sequence
from typing import cast

import httpx
import pydantic
from pydantic import TypeAdapter
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKAnalysisStatus,
    WDKAnalysisStatusResponse,
    WDKAnswer,
    WDKFilterValue,
    WDKRecordType,
    WDKSearch,
    WDKSearchResponse,
    WDKStep,
    WDKStepAnalysisConfig,
    WDKStepAnalysisType,
)
from veupath_chatbot.integrations.veupathdb.wdk_parameters import WDKParameter
from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.context import veupathdb_auth_token_ctx
from veupath_chatbot.platform.errors import WDKError, validate_response
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject, JSONValue

logger = get_logger(__name__)

_HTTP_SERVER_ERROR = 500


def encode_context_param_values_for_wdk(context: JSONObject) -> JSONObject:
    """Encode contextParamValues in the format WDK expects.

    Many WDK endpoints expect multi-pick values as JSON-encoded *strings*
    (e.g. '["a","b"]'), not arrays.

    :param context: Context dict.
    :returns: Encoded context suitable for WDK wire format.
    """
    encoded: JSONObject = {}
    for k, v in (context or {}).items():
        if v is None:
            continue
        if isinstance(v, str):
            encoded[k] = v
        elif isinstance(v, (list, dict)):
            encoded[k] = json.dumps(v)
        else:
            encoded[k] = str(v)
    return encoded


def _convert_params_for_httpx(
    params: JSONObject | None,
) -> (
    Mapping[
        str, str | int | float | bool | None | Sequence[str | int | float | bool | None]
    ]
    | None
):
    """Convert JSONObject params to format httpx expects.

    :param params: Optional params dict.
    :returns: Mapping suitable for httpx, or None if params is None.
    """
    if params is None:
        return None
    result: dict[
        str, str | int | float | bool | None | Sequence[str | int | float | bool | None]
    ] = {}
    for k, v in params.items():
        if v is None:
            result[k] = None
        elif isinstance(v, (str, int, float, bool)):
            result[k] = v
        elif isinstance(v, list):
            # Convert list to sequence of compatible types
            converted_list: list[str | int | float | bool | None] = []
            for item in v:
                if isinstance(item, (str, int, float, bool)) or item is None:
                    converted_list.append(item)
                else:
                    converted_list.append(str(item))
            result[k] = converted_list
        else:
            # Convert other types to string
            result[k] = str(v)
    return result


class VEuPathDBClient:
    """HTTP client for VEuPathDB WDK REST services."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        auth_token: str | None = None,
        *,
        max_connections: int = 1000,
        max_keepalive_connections: int = 200,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.auth_token = auth_token
        self.max_connections = int(max_connections)
        self.max_keepalive_connections = int(max_keepalive_connections)
        self._client: httpx.AsyncClient | None = None
        self._client_lock = asyncio.Lock()
        self._session_initialized = False

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is not None and not self._client.is_closed:
            return self._client
        async with self._client_lock:
            if self._client is None or self._client.is_closed:
                self._client = httpx.AsyncClient(
                    base_url=self.base_url,
                    timeout=httpx.Timeout(self.timeout),
                    follow_redirects=True,
                    limits=httpx.Limits(
                        max_connections=max(1, self.max_connections),
                        max_keepalive_connections=max(
                            0, self.max_keepalive_connections
                        ),
                    ),
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                )
            return self._client

    async def _init_wdk_session(self, client: httpx.AsyncClient) -> None:
        """Initialize a server-side WDK session (JSESSIONID).

        WDK process queries (e.g. GenesByOrthologPattern) require a Tomcat
        ``JSESSIONID`` established through the webapp.  Without it, process
        queries silently return 0 results.
        """
        webapp_url = self.base_url.replace("/service", "/app")
        try:
            await client.get(webapp_url, timeout=10)
            logger.debug(
                "WDK session initialized",
                jsessionid=bool(client.cookies.get("JSESSIONID")),
            )
        except httpx.HTTPError, OSError, RuntimeError:
            logger.debug("Failed to initialize WDK session (non-fatal)")

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    @retry(
        retry=retry_if_exception_type(
            (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError)
        ),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def _request_attempt(
        self,
        method: str,
        path: str,
        params: JSONObject | None = None,
        json: object = None,
    ) -> JSONValue:
        """Single HTTP request attempt (tenacity handles retries).

        Retries on transient errors: timeouts, connection failures, and
        server errors (5xx).  Client errors (4xx) are not retried.
        """
        client = await self._get_client()

        logger.debug(
            "VEuPathDB request",
            method=method,
            path=path,
            base_url=self.base_url,
        )

        try:
            settings = get_settings()
            auth_token = (
                veupathdb_auth_token_ctx.get()
                or self.auth_token
                or settings.veupathdb_auth_token
            )
            # WDK authenticates via an ``Authorization`` cookie (not a header).
            # Set the cookie on the client instance (not per-request) because
            # httpx has deprecated per-request ``cookies=``.
            if auth_token:
                client.cookies.set("Authorization", auth_token)
            # Initialize WDK session on first authenticated request.
            if auth_token and not self._session_initialized:
                self._session_initialized = True
                await self._init_wdk_session(client)
            httpx_params = _convert_params_for_httpx(params)
            response = await client.request(
                method=method,
                url=path,
                params=httpx_params,
                json=json,
            )
            response.raise_for_status()
            if not response.content or not response.text.strip():
                return None
            result = response.json()
            if result is None:
                return None
            return cast("JSONValue", result)
        except httpx.HTTPStatusError as e:
            allow = e.response.headers.get("allow") or e.response.headers.get("Allow")
            log_fn = (
                logger.warning
                if e.response.status_code >= _HTTP_SERVER_ERROR
                else logger.error
            )
            log_fn(
                "VEuPathDB HTTP error",
                method=method,
                status_code=e.response.status_code,
                path=path,
                allow=allow,
                response_text=e.response.text[:500],
            )
            # 5xx: re-raise so tenacity retries (up to 3 attempts).
            if e.response.status_code >= _HTTP_SERVER_ERROR:
                raise
            # 4xx: not retryable — convert to domain error immediately.
            msg = f"{method} {path} -> HTTP {e.response.status_code}: {e.response.text[:200]}"
            raise WDKError(
                msg,
                status=e.response.status_code,
            ) from e
        except httpx.TimeoutException, httpx.ConnectError:
            # Let tenacity retry these transient errors.
            raise
        except httpx.RequestError as e:
            logger.exception("VEuPathDB request error", error=str(e), path=path)
            msg = f"Request failed: {e}"
            raise WDKError(msg, status=502) from e

    async def _request(
        self,
        method: str,
        path: str,
        params: JSONObject | None = None,
        json: object = None,
    ) -> JSONValue:
        """Make HTTP request with retry logic.

        Wraps :meth:`_request_attempt` and converts tenacity ``RetryError``
        (raised when all retry attempts are exhausted) into ``WDKError``
        so callers only need to handle domain errors.
        """
        try:
            return await self._request_attempt(method, path, params=params, json=json)
        except RetryError as e:
            last = e.last_attempt.exception()
            status = 502
            if isinstance(last, httpx.HTTPStatusError):
                status = last.response.status_code
            log_fn = logger.warning if status >= _HTTP_SERVER_ERROR else logger.error
            log_fn(
                "VEuPathDB request failed after retries",
                method=method,
                path=path,
                error=str(last),
            )
            msg = f"Request failed after retries: {last}"
            raise WDKError(msg, status=status) from last

    async def get(self, path: str, params: JSONObject | None = None) -> JSONValue:
        """GET request."""
        return await self._request("GET", path, params=params)

    async def post(
        self,
        path: str,
        json: object = None,
        params: JSONObject | None = None,
    ) -> JSONValue:
        """POST request."""
        return await self._request("POST", path, params=params, json=json)

    async def patch(self, path: str, json: object = None) -> JSONValue:
        """PATCH request."""
        return await self._request("PATCH", path, json=json)

    async def put(self, path: str, json: object = None) -> JSONValue:
        """PUT request."""
        return await self._request("PUT", path, json=json)

    async def delete(self, path: str) -> JSONValue:
        """DELETE request."""
        return await self._request("DELETE", path)

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
            WDKSearchResponse, raw, f"WDK search response for {record_type}/{search_name}"
        )

    async def get_search_details_with_params(
        self,
        record_type: str,
        search_name: str,
        context: JSONObject,
        *,
        expand_params: bool = True,
    ) -> WDKSearchResponse:
        """Get detailed search configuration using provided parameters."""
        params: JSONObject | None = {"expandParams": "true"} if expand_params else None
        encoded_context = encode_context_param_values_for_wdk(context or {})
        raw = await self.post(
            f"/record-types/{record_type}/searches/{search_name}",
            json={"contextParamValues": encoded_context},
            params=params,
        )
        return validate_response(
            WDKSearchResponse, raw, f"WDK search response for {record_type}/{search_name}"
        )

    async def get_refreshed_dependent_params(
        self,
        record_type: str,
        search_name: str,
        param_name: str,
        context: JSONObject,
    ) -> list[WDKParameter]:
        """Refresh dependent params using WDK's refreshed-dependent-params endpoint.

        WDK's ``ParamContainerFormatter.getParamsJson()`` returns a JSON array
        of parameter objects.  Each item is parsed via the ``WDKParameter``
        discriminated union; items that fail validation are skipped.
        """
        encoded_context = encode_context_param_values_for_wdk(context or {})
        raw = await self.post(
            f"/record-types/{record_type}/searches/{search_name}/refreshed-dependent-params",
            json={
                "changedParam": {
                    "name": param_name,
                    "value": encoded_context.get(param_name, ""),
                },
                "contextParamValues": encoded_context,
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
        search_config: JSONObject,
        report_config: JSONObject | None = None,
    ) -> WDKAnswer:
        """Run a report on a search without creating a step or strategy.

        Uses WDK's anonymous report endpoint:
        ``POST /record-types/{recordType}/searches/{searchName}/reports/standard``

        This is significantly faster than creating steps/strategies because it
        requires no user session and can be parallelized.

        :param record_type: WDK record type (e.g. ``"transcript"``).
        :param search_name: WDK search name (e.g. ``"GenesByTaxon"``).
        :param search_config: Search config with ``parameters`` dict.
        :param report_config: Report config (pagination, attributes, etc.).
        :returns: Parsed ``WDKAnswer`` with typed ``meta`` and ``records``.
        """
        payload: JSONObject = {
            "searchConfig": search_config,
            "reportConfig": report_config or {},
        }
        result = await self.post(
            f"/record-types/{record_type}/searches/{search_name}/reports/standard",
            json=payload,
        )
        return validate_response(
            WDKAnswer, result, f"WDK answer for {record_type}/{search_name}"
        )

    async def get_step_view_filters(
        self, user_id: str, step_id: int
    ) -> list[WDKFilterValue]:
        """Get viewFilters from a step's searchConfig.

        WDK stores filters as ``searchConfig.viewFilters`` on the step resource.
        There is no dedicated ``/filter`` endpoint.
        """
        raw = await self.get(f"/users/{user_id}/steps/{step_id}")
        step = WDKStep.model_validate(raw)
        return list(step.search_config.view_filters)

    async def update_step_view_filters(
        self, user_id: str, step_id: int, filters: list[WDKFilterValue]
    ) -> JSONValue:
        """Update a step's viewFilters via PATCH on the step resource.

        WDK manages filters through ``answerSpec.viewFilters``. The PATCH
        body is ``{"answerSpec": {"viewFilters": [...]}}``.
        """
        return await self.patch(
            f"/users/{user_id}/steps/{step_id}",
            json={
                "answerSpec": {
                    "viewFilters": [
                        f.model_dump(by_alias=True) for f in filters
                    ],
                },
            },
        )

    async def list_analysis_types(
        self, user_id: str, step_id: int
    ) -> list[WDKStepAnalysisType]:
        """List available analysis types for a step."""
        raw = await self.get(f"/users/{user_id}/steps/{step_id}/analysis-types")
        if not isinstance(raw, list):
            return []
        result: list[WDKStepAnalysisType] = []
        for item in raw:
            if isinstance(item, dict):
                try:
                    result.append(WDKStepAnalysisType.model_validate(item))
                except pydantic.ValidationError:
                    logger.warning(
                        "Skipping unparseable analysis type",
                        error_keys=list(item.keys())[:5],
                    )
        return result

    async def get_analysis_type(
        self, user_id: str, step_id: int, analysis_type: str
    ) -> WDKStepAnalysisType:
        """Get analysis form metadata for a specific analysis type."""
        raw = await self.get(
            f"/users/{user_id}/steps/{step_id}/analysis-types/{analysis_type}"
        )
        return validate_response(
            WDKStepAnalysisType, raw, f"WDK analysis type response for {analysis_type}"
        )

    async def list_step_analyses(
        self, user_id: str, step_id: int
    ) -> list[WDKStepAnalysisConfig]:
        """List analyses that have been run on a step."""
        raw = await self.get(f"/users/{user_id}/steps/{step_id}/analyses")
        if not isinstance(raw, list):
            return []
        result: list[WDKStepAnalysisConfig] = []
        for item in raw:
            if isinstance(item, dict):
                try:
                    result.append(WDKStepAnalysisConfig.model_validate(item))
                except pydantic.ValidationError:
                    logger.warning(
                        "Skipping unparseable step analysis",
                        error_keys=list(item.keys())[:5],
                    )
        return result

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
    ) -> JSONObject:
        """Kick off execution of a step analysis instance.

        WDK step analyses are created first, then explicitly run.
        ``POST /users/{userId}/steps/{stepId}/analyses/{analysisId}/result``
        returns ``{"status": "RUNNING"|...}``.  The return value is
        typically unused — callers poll status separately.
        """
        raw = await self.post(
            f"/users/{user_id}/steps/{step_id}/analyses/{analysis_id}/result"
        )
        if isinstance(raw, dict):
            return raw
        return {}

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

        ``GET .../analyses/{analysisId}/result`` returns the analysis result
        JSON.  Returns 204 No Content if not yet complete.
        """
        raw = await self.get(
            f"/users/{user_id}/steps/{step_id}/analyses/{analysis_id}/result"
        )
        if isinstance(raw, dict):
            return raw
        return {}

    async def run_step_report(
        self,
        user_id: str,
        step_id: int,
        report_name: str,
        payload: JSONObject | None = None,
    ) -> JSONValue:
        """Run a report on a step."""
        return await self.post(
            f"/users/{user_id}/steps/{step_id}/reports/{report_name}",
            json=payload or {},
        )

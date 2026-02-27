"""HTTP client for VEuPathDB WDK REST API with retries and cookies."""

import json
from collections.abc import Mapping, Sequence
from typing import cast

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.context import veupathdb_auth_token_ctx
from veupath_chatbot.platform.errors import WDKError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue

logger = get_logger(__name__)


def _encode_context_param_values_for_wdk(context: JSONObject) -> JSONObject:
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


def encode_context_param_values_for_wdk(context: JSONObject) -> JSONObject:
    """Public helper: encode contextParamValues for WDK wire format.

    :param context: Context dict.
    :returns: Encoded context suitable for WDK wire format.
    """
    return _encode_context_param_values_for_wdk(context)


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

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True,
                limits=httpx.Limits(
                    max_connections=max(1, self.max_connections),
                    max_keepalive_connections=max(0, self.max_keepalive_connections),
                ),
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def _request(
        self,
        method: str,
        path: str,
        params: JSONObject | None = None,
        json: JSONObject | None = None,
    ) -> JSONValue:
        """Make HTTP request with retry logic."""
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
            extra_cookies = {"Authorization": auth_token} if auth_token else None
            httpx_params = _convert_params_for_httpx(params)
            response = await client.request(
                method=method,
                url=path,
                params=httpx_params,
                json=json,
                cookies=extra_cookies,
            )
            response.raise_for_status()
            if not response.content or not response.text.strip():
                return None
            result = response.json()
            # Ensure we return proper JSONValue type
            if result is None:
                return None
            return cast(JSONValue, result)
        except httpx.HTTPStatusError as e:
            allow = e.response.headers.get("allow") or e.response.headers.get("Allow")
            logger.error(
                "VEuPathDB HTTP error",
                method=method,
                status_code=e.response.status_code,
                path=path,
                allow=allow,
                response_text=e.response.text[:500],
            )
            raise WDKError(
                f"{method} {path} -> HTTP {e.response.status_code}: {e.response.text[:200]}",
                status=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            logger.error("VEuPathDB request error", error=str(e), path=path)
            raise WDKError(f"Request failed: {e}", status=502) from e

    async def get(self, path: str, params: JSONObject | None = None) -> JSONValue:
        """GET request."""
        return await self._request("GET", path, params=params)

    async def post(
        self,
        path: str,
        json: JSONObject | None = None,
        params: JSONObject | None = None,
    ) -> JSONValue:
        """POST request."""
        return await self._request("POST", path, params=params, json=json)

    async def patch(self, path: str, json: JSONObject | None = None) -> JSONValue:
        """PATCH request."""
        return await self._request("PATCH", path, json=json)

    async def put(self, path: str, json: JSONObject | None = None) -> JSONValue:
        """PUT request."""
        return await self._request("PUT", path, json=json)

    async def delete(self, path: str) -> JSONValue:
        """DELETE request."""
        return await self._request("DELETE", path)

    async def get_record_types(self, expanded: bool = False) -> JSONArray:
        """Get available record types."""
        params: JSONObject | None = {"format": "expanded"} if expanded else None
        return cast(JSONArray, await self.get("/record-types", params=params))

    async def get_searches(self, record_type: str) -> JSONArray:
        """Get searches for a record type."""
        return cast(JSONArray, await self.get(f"/record-types/{record_type}/searches"))

    async def get_search_details(
        self,
        record_type: str,
        search_name: str,
        expand_params: bool = True,
    ) -> JSONObject:
        """Get detailed search configuration including parameters."""
        params: JSONObject | None = {"expandParams": "true"} if expand_params else None
        return cast(
            JSONObject,
            await self.get(
                f"/record-types/{record_type}/searches/{search_name}",
                params=params,
            ),
        )

    async def get_search_details_with_params(
        self,
        record_type: str,
        search_name: str,
        context: JSONObject,
        expand_params: bool = True,
    ) -> JSONObject:
        """Get detailed search configuration using provided parameters."""
        params: JSONObject | None = {"expandParams": "true"} if expand_params else None
        encoded_context = _encode_context_param_values_for_wdk(context or {})
        return cast(
            JSONObject,
            await self.post(
                f"/record-types/{record_type}/searches/{search_name}",
                json={"contextParamValues": encoded_context},
                params=params,
            ),
        )

    async def get_question_parameter_values(
        self,
        record_type: str,
        search_name: str,
        param_name: str,
        context: JSONObject | None = None,
    ) -> JSONObject:
        """Get vocabulary values for a dependent parameter."""
        return await self.get_refreshed_dependent_params(
            record_type,
            search_name,
            param_name,
            context or {},
        )

    async def get_refreshed_dependent_params(
        self,
        record_type: str,
        search_name: str,
        param_name: str,
        context: JSONObject,
    ) -> JSONObject:
        """Refresh dependent params using WDK's refreshed-dependent-params endpoint."""
        encoded_context = _encode_context_param_values_for_wdk(context or {})
        return cast(
            JSONObject,
            await self.post(
                f"/record-types/{record_type}/searches/{search_name}/refreshed-dependent-params",
                json={
                    "changedParam": {
                        "name": param_name,
                        "value": encoded_context.get(param_name, ""),
                    },
                    "contextParamValues": encoded_context,
                },
            ),
        )

    async def get_ontology_term_summary(
        self, record_type: str, ontology: str
    ) -> JSONObject:
        """Get ontology term summary for filtering."""
        return cast(
            JSONObject,
            await self.get(
                f"/record-types/{record_type}/ontology/{ontology}/term-summary"
            ),
        )

    async def list_step_filters(self, user_id: str, step_id: int) -> JSONArray:
        """List filters applied to a step."""
        return cast(
            JSONArray, await self.get(f"/users/{user_id}/steps/{step_id}/filter")
        )

    async def set_step_filter(
        self,
        user_id: str,
        step_id: int,
        filter_name: str,
        payload: JSONObject,
    ) -> JSONValue:
        """Create or update a filter on a step."""
        return await self.put(
            f"/users/{user_id}/steps/{step_id}/filter/{filter_name}",
            json=payload,
        )

    async def delete_step_filter(
        self, user_id: str, step_id: int, filter_name: str
    ) -> JSONValue:
        """Remove a filter from a step."""
        return await self.delete(
            f"/users/{user_id}/steps/{step_id}/filter/{filter_name}"
        )

    async def list_analysis_types(self, user_id: str, step_id: int) -> JSONArray:
        """List available analysis types for a step."""
        return cast(
            JSONArray,
            await self.get(f"/users/{user_id}/steps/{step_id}/analysis-types"),
        )

    async def get_analysis_type(
        self, user_id: str, step_id: int, analysis_type: str
    ) -> JSONObject:
        """Get analysis form metadata for a specific analysis type."""
        return cast(
            JSONObject,
            await self.get(
                f"/users/{user_id}/steps/{step_id}/analysis-types/{analysis_type}"
            ),
        )

    async def list_step_analyses(self, user_id: str, step_id: int) -> JSONArray:
        """List analyses that have been run on a step."""
        return cast(
            JSONArray, await self.get(f"/users/{user_id}/steps/{step_id}/analyses")
        )

    async def create_step_analysis(
        self, user_id: str, step_id: int, payload: JSONObject
    ) -> JSONObject:
        """Create a new analysis instance for a step."""
        return cast(
            JSONObject,
            await self.post(f"/users/{user_id}/steps/{step_id}/analyses", json=payload),
        )

    async def run_analysis_instance(
        self, user_id: str, step_id: int, analysis_id: int
    ) -> JSONObject:
        """Kick off execution of a step analysis instance.

        WDK step analyses are created first, then explicitly run.
        ``POST /users/{userId}/steps/{stepId}/analyses/{analysisId}/result``
        returns ``{"status": "RUNNING"|...}``.
        """
        return cast(
            JSONObject,
            await self.post(
                f"/users/{user_id}/steps/{step_id}/analyses/{analysis_id}/result"
            ),
        )

    async def get_analysis_status(
        self, user_id: str, step_id: int, analysis_id: int
    ) -> JSONObject:
        """Poll execution status of a step analysis instance.

        ``GET .../analyses/{analysisId}/result/status`` returns
        ``{"status": "RUNNING"|"COMPLETE"|"ERROR"|...}``.
        """
        return cast(
            JSONObject,
            await self.get(
                f"/users/{user_id}/steps/{step_id}/analyses/{analysis_id}/result/status"
            ),
        )

    async def get_analysis_result(
        self, user_id: str, step_id: int, analysis_id: int
    ) -> JSONObject:
        """Get the result of a completed step analysis instance.

        ``GET .../analyses/{analysisId}/result`` returns the analysis result
        JSON.  Returns 204 No Content if not yet complete.
        """
        return cast(
            JSONObject,
            await self.get(
                f"/users/{user_id}/steps/{step_id}/analyses/{analysis_id}/result"
            ),
        )

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

    async def get_step_filter_summary(
        self, user_id: str, step_id: int, filter_name: str
    ) -> JSONObject:
        """Get filter summary data for a step."""
        return cast(
            JSONObject,
            await self.get(
                f"/users/{user_id}/steps/{step_id}/filter-summary/{filter_name}"
            ),
        )

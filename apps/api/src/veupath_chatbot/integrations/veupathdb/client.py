"""HTTP client for VEuPathDB WDK REST API with retries and cookies."""

from typing import Any

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

logger = get_logger(__name__)


class VEuPathDBClient:
    """HTTP client for VEuPathDB WDK REST services."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        auth_token: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.auth_token = auth_token
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True,
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
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
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
            auth_token = veupathdb_auth_token_ctx.get() or self.auth_token or settings.veupathdb_auth_token
            extra_cookies = {"Authorization": auth_token} if auth_token else None
            response = await client.request(
                method=method,
                url=path,
                params=params,
                json=json,
                cookies=extra_cookies,
            )
            response.raise_for_status()
            if not response.content or not response.text.strip():
                return None
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                "VEuPathDB HTTP error",
                status_code=e.response.status_code,
                path=path,
                response_text=e.response.text[:500],
            )
            raise WDKError(
                f"HTTP {e.response.status_code}: {e.response.text[:200]}",
                status=e.response.status_code,
            )
        except httpx.RequestError as e:
            logger.error("VEuPathDB request error", error=str(e), path=path)
            raise WDKError(f"Request failed: {e}", status=502)

    async def get(
        self, path: str, params: dict[str, Any] | None = None
    ) -> Any:
        """GET request."""
        return await self._request("GET", path, params=params)

    async def post(
        self,
        path: str,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """POST request."""
        return await self._request("POST", path, params=params, json=json)

    async def patch(
        self, path: str, json: dict[str, Any] | None = None
    ) -> Any:
        """PATCH request."""
        return await self._request("PATCH", path, json=json)

    async def put(self, path: str, json: dict[str, Any] | None = None) -> Any:
        """PUT request."""
        return await self._request("PUT", path, json=json)

    async def delete(self, path: str) -> Any:
        """DELETE request."""
        return await self._request("DELETE", path)

    # =========================================================================
    # High-level API methods
    # =========================================================================

    async def get_record_types(self, expanded: bool = False) -> list[dict[str, Any]]:
        """Get available record types."""
        params = {"format": "expanded"} if expanded else None
        return await self.get("/record-types", params=params)

    async def get_searches(self, record_type: str) -> list[dict[str, Any]]:
        """Get searches for a record type."""
        return await self.get(f"/record-types/{record_type}/searches")

    async def get_search_details(
        self,
        record_type: str,
        search_name: str,
        expand_params: bool = True,
    ) -> dict[str, Any]:
        """Get detailed search configuration including parameters."""
        params = {"expandParams": "true"} if expand_params else None
        return await self.get(
            f"/record-types/{record_type}/searches/{search_name}",
            params=params,
        )

    async def get_search_details_with_params(
        self,
        record_type: str,
        search_name: str,
        context: dict[str, Any],
        expand_params: bool = True,
    ) -> dict[str, Any]:
        """Get detailed search configuration using provided parameters."""
        params = {"expandParams": "true"} if expand_params else None
        return await self.post(
            f"/record-types/{record_type}/searches/{search_name}",
            json={"contextParamValues": context},
            params=params,
        )

    async def get_question_parameter_values(
        self,
        record_type: str,
        search_name: str,
        param_name: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
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
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Refresh dependent params using WDK's refreshed-dependent-params endpoint."""
        return await self.post(
            f"/record-types/{record_type}/searches/{search_name}/refreshed-dependent-params",
            json={
                "changedParam": {
                    "name": param_name,
                    "value": context.get(param_name, ""),
                },
                "contextParamValues": context,
            },
        )

    async def get_ontology_term_summary(
        self, record_type: str, ontology: str
    ) -> dict[str, Any]:
        """Get ontology term summary for filtering."""
        return await self.get(
            f"/record-types/{record_type}/ontology/{ontology}/term-summary"
        )

    # =========================================================================
    # Step filters, analyses, reports
    # =========================================================================

    async def list_step_filters(self, user_id: str, step_id: int) -> list[dict[str, Any]]:
        """List filters applied to a step."""
        return await self.get(f"/users/{user_id}/steps/{step_id}/filter")

    async def set_step_filter(
        self,
        user_id: str,
        step_id: int,
        filter_name: str,
        payload: dict[str, Any],
    ) -> Any:
        """Create or update a filter on a step."""
        return await self.put(
            f"/users/{user_id}/steps/{step_id}/filter/{filter_name}",
            json=payload,
        )

    async def delete_step_filter(self, user_id: str, step_id: int, filter_name: str) -> Any:
        """Remove a filter from a step."""
        return await self.delete(
            f"/users/{user_id}/steps/{step_id}/filter/{filter_name}"
        )

    async def list_analysis_types(self, user_id: str, step_id: int) -> list[dict[str, Any]]:
        """List available analysis types for a step."""
        return await self.get(f"/users/{user_id}/steps/{step_id}/analysis-types")

    async def get_analysis_type(
        self, user_id: str, step_id: int, analysis_type: str
    ) -> dict[str, Any]:
        """Get analysis form metadata for a specific analysis type."""
        return await self.get(
            f"/users/{user_id}/steps/{step_id}/analysis-types/{analysis_type}"
        )

    async def list_step_analyses(self, user_id: str, step_id: int) -> list[dict[str, Any]]:
        """List analyses that have been run on a step."""
        return await self.get(f"/users/{user_id}/steps/{step_id}/analyses")

    async def create_step_analysis(
        self, user_id: str, step_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Create a new analysis instance for a step."""
        return await self.post(
            f"/users/{user_id}/steps/{step_id}/analyses", json=payload
        )

    async def run_step_report(
        self,
        user_id: str,
        step_id: int,
        report_name: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        """Run a report on a step."""
        return await self.post(
            f"/users/{user_id}/steps/{step_id}/reports/{report_name}",
            json=payload or {},
        )

    async def get_step_filter_summary(
        self, user_id: str, step_id: int, filter_name: str
    ) -> dict[str, Any]:
        """Get filter summary data for a step."""
        return await self.get(
            f"/users/{user_id}/steps/{step_id}/reports/filter-summary/{filter_name}"
        )


"""Core HTTP transport for VEuPathDB WDK REST API with retries and cookies."""

import asyncio
import time
from collections.abc import Mapping, Sequence
from typing import cast

import httpx
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from pathfinder.integrations.veupathdb._observability import (
    WdkRequestTelemetry,
    log_wdk_retry,
)
from pathfinder.platform.config import get_settings
from pathfinder.platform.context import veupathdb_auth_token_ctx
from pathfinder.platform.errors import WDKError
from pathfinder.platform.logging import get_logger
from pathfinder.platform.metrics import wdk_request_duration_s, wdk_requests
from pathfinder.platform.types import JSONObject, JSONValue

logger = get_logger(__name__)

_HTTP_SERVER_ERROR = 500


def _inject_auth_cookie(request: httpx.Request, auth_token: str) -> None:
    """Append an ``Authorization`` cookie to a built request.

    Modifies only the per-request :class:`httpx.Request` object — never the
    shared :class:`httpx.AsyncClient` cookie jar — so concurrent requests
    with different auth tokens cannot interfere with each other.
    """
    existing = request.headers.get("cookie", "")
    auth_cookie = f"Authorization={auth_token}"
    if existing:
        request.headers["cookie"] = f"{existing}; {auth_cookie}"
    else:
        request.headers["cookie"] = auth_cookie


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


class HTTPClient:
    """Low-level HTTP transport for VEuPathDB WDK REST services."""

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

    async def _init_wdk_session(
        self, client: httpx.AsyncClient, auth_token: str
    ) -> None:
        """Initialize a server-side WDK session (JSESSIONID).

        WDK process queries (e.g. GenesByOrthologPattern) require a Tomcat
        ``JSESSIONID`` established through the webapp.  Without it, process
        queries silently return 0 results.
        """
        webapp_url = self.base_url.replace("/service", "/app")
        try:
            request = client.build_request("GET", webapp_url, timeout=10)
            _inject_auth_cookie(request, auth_token)
            await client.send(request)
            logger.debug(
                "WDK session initialized",
                jsessionid=bool(client.cookies.get("JSESSIONID")),
            )
        except httpx.HTTPError, OSError, RuntimeError:
            logger.debug("Failed to initialize WDK session (non-fatal)")

    async def close(self) -> None:
        """Close HTTP client and reset session state.

        The JSESSIONID lives on the httpx client's cookie jar, so a new
        client must re-initialize the WDK session to avoid process queries
        silently returning 0 results.
        """
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
        self._session_initialized = False

    @retry(
        retry=retry_if_exception_type(
            (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError)
        ),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        before_sleep=log_wdk_retry,
    )
    async def _request_attempt(
        self,
        method: str,
        path: str,
        params: JSONObject | None = None,
        json: object = None,
    ) -> JSONValue:
        """Single HTTP request attempt (tenacity handles retries)."""
        client = await self._get_client()
        auth_token = (
            veupathdb_auth_token_ctx.get()
            or self.auth_token
            or get_settings().veupathdb_auth_token
        )
        telemetry = WdkRequestTelemetry(
            method=method,
            path=path,
            base_url=self.base_url,
            has_auth=bool(auth_token),
        )

        logger.debug(
            "VEuPathDB request",
            method=method,
            path=path,
            base_url=self.base_url,
            endpoint_group=telemetry.metric_attrs(outcome="pending")["endpoint_group"],
        )

        try:
            # WDK authenticates via an ``Authorization`` cookie (not a header).
            # Inject per-request into the built Request object to avoid
            # mutating the shared client cookie jar (which would race
            # between concurrent users on the same site).
            if auth_token and not self._session_initialized:
                self._session_initialized = True
                await self._init_wdk_session(client, auth_token)
            httpx_params = _convert_params_for_httpx(params)
            request = client.build_request(
                method=method,
                url=path,
                params=httpx_params,
                json=json,
            )
            if auth_token:
                _inject_auth_cookie(request, auth_token)
            response = await client.send(request)
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
        """Make HTTP request with retry logic (converts RetryError to WDKError)."""
        start = time.monotonic()
        auth_token = (
            veupathdb_auth_token_ctx.get()
            or self.auth_token
            or get_settings().veupathdb_auth_token
        )
        telemetry = WdkRequestTelemetry(
            method=method,
            path=path,
            base_url=self.base_url,
            has_auth=bool(auth_token),
        )
        try:
            result = await self._request_attempt(
                method, path, params=params, json=json,
            )
        except RetryError as e:
            last = e.last_attempt.exception()
            status_code = None
            if isinstance(last, httpx.HTTPStatusError):
                status_code = last.response.status_code
            metric_attrs = telemetry.metric_attrs(
                outcome="error",
                status_code=status_code,
            )
            wdk_requests.add(1, metric_attrs)
            wdk_request_duration_s.record(time.monotonic() - start, metric_attrs)
            status = 502
            if isinstance(last, httpx.HTTPStatusError):
                status = last.response.status_code
            log_fn = logger.warning if status >= _HTTP_SERVER_ERROR else logger.error
            log_fn(
                "VEuPathDB request failed after retries",
                method=method,
                path=path,
                endpoint_group=metric_attrs["endpoint_group"],
                site_host=metric_attrs["site_host"],
                error=str(last),
            )
            msg = f"Request failed after retries: {last}"
            raise WDKError(msg, status=status) from last
        except WDKError as error:
            metric_attrs = telemetry.metric_attrs(
                outcome="error",
                status_code=error.status,
            )
            wdk_requests.add(1, metric_attrs)
            wdk_request_duration_s.record(time.monotonic() - start, metric_attrs)
            raise
        else:
            metric_attrs = telemetry.metric_attrs(outcome="ok", status_code=200)
            wdk_requests.add(1, metric_attrs)
            wdk_request_duration_s.record(time.monotonic() - start, metric_attrs)
            return result

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

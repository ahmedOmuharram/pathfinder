"""Observability helpers for VEuPathDB HTTP clients."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
from tenacity import RetryCallState

from pathfinder.platform.logging import get_logger
from pathfinder.platform.metrics import site_search_request_retries, wdk_request_retries

logger = get_logger(__name__)
_RETRY_STATE_REQUIRED_ARGS = 3
_ENDPOINT_GROUP_PREFIXES = (
    ("record-types/", "record_types"),
    ("searches/", "searches"),
    ("strategies/", "strategies"),
    ("steps/", "steps"),
    ("answers/", "answers"),
    ("users/", "users"),
    ("reports/", "reports"),
    ("site-search", "site_search"),
)


def _status_family(status_code: int | None) -> str:
    if status_code is None:
        return "none"
    return f"{status_code // 100}xx"


def _site_host(base_url: str) -> str:
    return urlparse(base_url).hostname or "unknown"


def _endpoint_group(path: str) -> str:
    normalized = path.lstrip("/")
    for prefix, group in _ENDPOINT_GROUP_PREFIXES:
        if normalized.startswith(prefix):
            return group
    return "other"


def _error_kind(error: BaseException) -> str:
    if isinstance(error, httpx.TimeoutException):
        return "timeout"
    if isinstance(error, httpx.ConnectError):
        return "connect_error"
    if isinstance(error, httpx.HTTPStatusError):
        return f"http_{_status_family(error.response.status_code)}"
    if isinstance(error, httpx.RequestError):
        return "request_error"
    return type(error).__name__


@dataclass(frozen=True)
class _RequestMetricContext:
    method: str
    path: str
    base_url: str
    has_auth: bool


def _request_metric_attrs(
    *,
    context: _RequestMetricContext,
    outcome: str,
    status_code: int | None = None,
    retried: bool | None = None,
) -> dict[str, str]:
    attrs = {
        "method": context.method,
        "endpoint_group": _endpoint_group(context.path),
        "site_host": _site_host(context.base_url),
        "has_auth": str(context.has_auth).lower(),
        "status_family": _status_family(status_code),
        "outcome": outcome,
    }
    if retried is not None:
        attrs["retried"] = str(retried).lower()
    return attrs


@dataclass(frozen=True)
class WdkRequestTelemetry:
    """Low-cardinality observability context for one logical WDK request."""

    method: str
    path: str
    base_url: str
    has_auth: bool

    def metric_attrs(
        self,
        *,
        outcome: str,
        status_code: int | None = None,
        retried: bool | None = None,
    ) -> dict[str, str]:
        return _request_metric_attrs(
            context=_RequestMetricContext(
                method=self.method,
                path=self.path,
                base_url=self.base_url,
                has_auth=self.has_auth,
            ),
            outcome=outcome,
            status_code=status_code,
            retried=retried,
        )


@dataclass(frozen=True)
class SiteSearchRequestTelemetry:
    """Low-cardinality observability context for one logical site-search request."""

    method: str
    path: str
    base_url: str

    def metric_attrs(
        self,
        *,
        outcome: str,
        status_code: int | None = None,
        retried: bool | None = None,
    ) -> dict[str, str]:
        return _request_metric_attrs(
            context=_RequestMetricContext(
                method=self.method,
                path=self.path,
                base_url=self.base_url,
                has_auth=False,
            ),
            outcome=outcome,
            status_code=status_code,
            retried=retried,
        )


def log_wdk_retry(retry_state: RetryCallState) -> None:
    """Record retry metrics and logs for transient WDK failures."""
    if len(retry_state.args) < _RETRY_STATE_REQUIRED_ARGS:
        return
    client = retry_state.args[0]
    method = retry_state.args[1]
    path = retry_state.args[2]
    if (
        not isinstance(client, object)
        or not isinstance(method, str)
        or not isinstance(path, str)
    ):
        return

    next_action = retry_state.next_action
    if next_action is None:
        return
    outcome = retry_state.outcome
    if outcome is None or not outcome.failed:
        return
    error = outcome.exception()
    if error is None:
        return

    telemetry = WdkRequestTelemetry(
        method=method,
        path=path,
        base_url=getattr(client, "base_url", ""),
        has_auth=bool(getattr(client, "auth_token", None)),
    )
    attrs = telemetry.metric_attrs(
        outcome="retry",
        status_code=(
            error.response.status_code
            if isinstance(error, httpx.HTTPStatusError)
            else None
        ),
        retried=True,
    )
    wdk_request_retries.add(1, attrs | {"error_kind": _error_kind(error)})
    logger.warning(
        "Retrying VEuPathDB request",
        method=method,
        path=path,
        endpoint_group=attrs["endpoint_group"],
        site_host=attrs["site_host"],
        attempt=retry_state.attempt_number,
        wait_seconds=next_action.sleep,
        error_kind=_error_kind(error),
        error=str(error),
    )


def log_site_search_retry(retry_state: RetryCallState) -> None:
    """Record retry metrics and logs for transient site-search failures."""
    if len(retry_state.args) < _RETRY_STATE_REQUIRED_ARGS:
        return
    client = retry_state.args[0]
    if not isinstance(client, object):
        return
    next_action = retry_state.next_action
    if next_action is None:
        return
    outcome = retry_state.outcome
    if outcome is None or not outcome.failed:
        return
    error = outcome.exception()
    if error is None:
        return

    telemetry = SiteSearchRequestTelemetry(
        method="POST",
        path="/site-search",
        base_url=getattr(client, "_base_url", ""),
    )
    attrs = telemetry.metric_attrs(outcome="retry", retried=True)
    site_search_request_retries.add(1, attrs | {"error_kind": _error_kind(error)})
    logger.warning(
        "Retrying site-search request",
        endpoint_group=attrs["endpoint_group"],
        site_host=attrs["site_host"],
        attempt=retry_state.attempt_number,
        wait_seconds=next_action.sleep,
        error_kind=_error_kind(error),
        error=str(error),
    )

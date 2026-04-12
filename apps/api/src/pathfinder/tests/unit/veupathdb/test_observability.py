"""Tests for WDK HTTP observability helpers."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from pathfinder.integrations.veupathdb._observability import (
    SiteSearchRequestTelemetry,
    WdkRequestTelemetry,
    log_site_search_retry,
    log_wdk_retry,
)
from pathfinder.integrations.veupathdb.site_search_client import (
    SiteSearchClient,
    SiteSearchResponse,
)
from pathfinder.platform.errors import AppError, ErrorCode


def test_wdk_request_telemetry_builds_low_cardinality_attrs() -> None:
    telemetry = WdkRequestTelemetry(
        method="GET",
        path="/record-types/gene/searches/GenesByText",
        base_url="https://plasmodb.org/plasmo/service",
        has_auth=True,
    )

    attrs = telemetry.metric_attrs(outcome="ok", status_code=200, retried=False)

    assert attrs == {
        "method": "GET",
        "endpoint_group": "record_types",
        "site_host": "plasmodb.org",
        "has_auth": "true",
        "status_family": "2xx",
        "outcome": "ok",
        "retried": "false",
    }


def test_log_wdk_retry_records_retry_metric_and_warning() -> None:
    retry_state = SimpleNamespace(
        args=(
            SimpleNamespace(
                base_url="https://plasmodb.org/plasmo/service",
                auth_token="secret",
            ),
            "GET",
            "/record-types/gene/searches/GenesByText",
        ),
        next_action=SimpleNamespace(sleep=2.0),
        outcome=SimpleNamespace(
            failed=True,
            exception=lambda: httpx.ConnectError("connection refused"),
        ),
        attempt_number=2,
    )

    with (
        patch("pathfinder.integrations.veupathdb._observability.wdk_request_retries") as mock_retries,
        patch("pathfinder.integrations.veupathdb._observability.logger") as mock_logger,
    ):
        log_wdk_retry(retry_state)

    mock_retries.add.assert_called_once_with(
        1,
        {
            "method": "GET",
            "endpoint_group": "record_types",
            "site_host": "plasmodb.org",
            "has_auth": "true",
            "status_family": "none",
            "outcome": "retry",
            "retried": "true",
            "error_kind": "connect_error",
        },
    )
    mock_logger.warning.assert_called_once()


def test_site_search_request_telemetry_builds_expected_attrs() -> None:
    telemetry = SiteSearchRequestTelemetry(
        method="POST",
        path="/site-search",
        base_url="https://plasmodb.org",
    )

    attrs = telemetry.metric_attrs(outcome="ok", status_code=200, retried=False)

    assert attrs == {
        "method": "POST",
        "endpoint_group": "site_search",
        "site_host": "plasmodb.org",
        "has_auth": "false",
        "status_family": "2xx",
        "outcome": "ok",
        "retried": "false",
    }


def test_log_site_search_retry_records_retry_metric_and_warning() -> None:
    retry_state = SimpleNamespace(
        args=(SimpleNamespace(_base_url="https://plasmodb.org"), "transporters", [], [], 20, 0),
        next_action=SimpleNamespace(sleep=1.5),
        outcome=SimpleNamespace(
            failed=True,
            exception=lambda: httpx.TimeoutException("timeout"),
        ),
        attempt_number=2,
    )

    with (
        patch(
            "pathfinder.integrations.veupathdb._observability.site_search_request_retries"
        ) as mock_retries,
        patch("pathfinder.integrations.veupathdb._observability.logger") as mock_logger,
    ):
        log_site_search_retry(retry_state)

    mock_retries.add.assert_called_once_with(
        1,
        {
            "method": "POST",
            "endpoint_group": "site_search",
            "site_host": "plasmodb.org",
            "has_auth": "false",
            "status_family": "none",
            "outcome": "retry",
            "retried": "true",
            "error_kind": "timeout",
        },
    )
    mock_logger.warning.assert_called_once()


@pytest.mark.asyncio
async def test_site_search_client_records_success_metrics() -> None:
    client = SiteSearchClient("https://plasmodb.org", "PlasmoDB")
    response = SiteSearchResponse()

    with (
        patch.object(client, "_search_with_retry", AsyncMock(return_value=response)),
        patch(
            "pathfinder.integrations.veupathdb.site_search_client.site_search_requests"
        ) as mock_requests,
        patch(
            "pathfinder.integrations.veupathdb.site_search_client.site_search_request_duration_s"
        ) as mock_duration,
        patch(
            "pathfinder.integrations.veupathdb.site_search_client.time.monotonic",
            side_effect=[10.0, 12.0],
        ),
    ):
        result = await client.search("transporter")

    assert result is response
    expected_attrs = {
        "method": "POST",
        "endpoint_group": "site_search",
        "site_host": "plasmodb.org",
        "has_auth": "false",
        "status_family": "2xx",
        "outcome": "ok",
    }
    mock_requests.add.assert_called_once_with(1, expected_attrs)
    mock_duration.record.assert_called_once_with(2.0, expected_attrs)


@pytest.mark.asyncio
async def test_site_search_client_records_error_metrics() -> None:
    client = SiteSearchClient("https://plasmodb.org", "PlasmoDB")
    error = AppError(ErrorCode.WDK_ERROR, "site-search failed")

    with (
        patch.object(client, "_search_with_retry", AsyncMock(side_effect=error)),
        patch(
            "pathfinder.integrations.veupathdb.site_search_client.site_search_requests"
        ) as mock_requests,
        patch(
            "pathfinder.integrations.veupathdb.site_search_client.site_search_request_duration_s"
        ) as mock_duration,
        patch(
            "pathfinder.integrations.veupathdb.site_search_client.time.monotonic",
            side_effect=[10.0, 10.5],
        ),
        pytest.raises(AppError, match="site-search failed"),
    ):
        await client.search("transporter")

    expected_attrs = {
        "method": "POST",
        "endpoint_group": "site_search",
        "site_host": "plasmodb.org",
        "has_auth": "false",
        "status_family": "none",
        "outcome": "error",
    }
    mock_requests.add.assert_called_once_with(1, expected_attrs)
    mock_duration.record.assert_called_once_with(0.5, expected_attrs)

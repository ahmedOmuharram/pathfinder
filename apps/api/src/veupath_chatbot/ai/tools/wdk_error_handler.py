"""Shared WDK step error handling for result-fetching tools."""

import http

from veupath_chatbot.platform.errors import ErrorCode, WDKError
from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.platform.types import JSONObject

_HTTP_NOT_FOUND = http.HTTPStatus.NOT_FOUND
_HTTP_BAD_REQUEST = http.HTTPStatus.BAD_REQUEST
_HTTP_UNAUTHORIZED = http.HTTPStatus.UNAUTHORIZED
_HTTP_FORBIDDEN = http.HTTPStatus.FORBIDDEN
_HTTP_INTERNAL_SERVER_ERROR = http.HTTPStatus.INTERNAL_SERVER_ERROR


def _handle_not_found(wdk_step_id: int, status: int) -> JSONObject:
    return tool_error(
        ErrorCode.WDK_ERROR,
        "Step not found in VEuPathDB. The step ID may be stale, from a different session, or not built yet. Build/rebuild the strategy and use a fresh step ID from this run.",
        wdk_step_id=wdk_step_id,
        http_status=status,
    )


def _handle_bad_request(wdk_step_id: int, status: int) -> JSONObject:
    return tool_error(
        ErrorCode.WDK_ERROR,
        "VEuPathDB rejected the download request payload (missing/invalid reportName). This is a server integration issue, not your step data.",
        wdk_step_id=wdk_step_id,
        http_status=status,
    )


def _handle_auth_error(wdk_step_id: int, status: int, action: str) -> JSONObject:
    return tool_error(
        ErrorCode.WDK_ERROR,
        f"Not authorized to {action} this step in VEuPathDB. Re-authenticate and retry, or use a step ID from your own strategy.",
        wdk_step_id=wdk_step_id,
        http_status=status,
    )


def _handle_server_error(
    wdk_step_id: int, status: int, fallback_message: str
) -> JSONObject:
    return tool_error(
        ErrorCode.WDK_ERROR,
        f"VEuPathDB is temporarily unavailable while {fallback_message}. Please retry in a moment.",
        wdk_step_id=wdk_step_id,
        http_status=status,
    )


def _handle_specific_status(
    e: WDKError,
    wdk_step_id: int,
    action: str,
    fallback_message: str,
) -> JSONObject | None:
    """Handle 404 and 400/reportName specifically; return None for others."""
    if e.status == _HTTP_NOT_FOUND:
        return _handle_not_found(wdk_step_id, e.status)
    if e.status == _HTTP_BAD_REQUEST and "reportName" in (e.detail or ""):
        return _handle_bad_request(wdk_step_id, e.status)
    return _handle_auth_or_server_error(e, wdk_step_id, action, fallback_message)


def _handle_auth_or_server_error(
    e: WDKError,
    wdk_step_id: int,
    action: str,
    fallback_message: str,
) -> JSONObject | None:
    """Handle auth and server errors; return None for generic cases."""
    if e.status in (_HTTP_UNAUTHORIZED, _HTTP_FORBIDDEN):
        return _handle_auth_error(wdk_step_id, e.status, action)
    if e.status >= _HTTP_INTERNAL_SERVER_ERROR:
        return _handle_server_error(wdk_step_id, e.status, fallback_message)
    return None


def handle_wdk_step_error(
    e: WDKError,
    *,
    wdk_step_id: int,
    action: str,
    fallback_message: str,
) -> JSONObject:
    specific = _handle_specific_status(e, wdk_step_id, action, fallback_message)
    return (
        specific
        if specific is not None
        else tool_error(
            ErrorCode.WDK_ERROR,
            f"VEuPathDB rejected request for step {wdk_step_id}: {e.detail}",
            wdk_step_id=wdk_step_id,
            http_status=e.status,
        )
    )

"""Shared WDK step error handling for result-fetching tools."""

from veupath_chatbot.platform.errors import ErrorCode, WDKError
from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.platform.types import JSONObject


def handle_wdk_step_error(
    e: WDKError,
    *,
    wdk_step_id: int,
    action: str,
    fallback_message: str,
) -> JSONObject:
    if e.status == 404:
        return tool_error(
            ErrorCode.WDK_ERROR,
            "Step not found in VEuPathDB. The step ID may be stale, from a different session, or not built yet. Build/rebuild the strategy and use a fresh step ID from this run.",
            wdk_step_id=wdk_step_id,
            http_status=e.status,
        )
    if e.status == 400 and "reportName" in (e.detail or ""):
        return tool_error(
            ErrorCode.WDK_ERROR,
            "VEuPathDB rejected the download request payload (missing/invalid reportName). This is a server integration issue, not your step data.",
            wdk_step_id=wdk_step_id,
            http_status=e.status,
        )
    if e.status in (401, 403):
        return tool_error(
            ErrorCode.WDK_ERROR,
            f"Not authorized to {action} this step in VEuPathDB. Re-authenticate and retry, or use a step ID from your own strategy.",
            wdk_step_id=wdk_step_id,
            http_status=e.status,
        )
    if e.status >= 500:
        return tool_error(
            ErrorCode.WDK_ERROR,
            f"VEuPathDB is temporarily unavailable while {fallback_message}. Please retry in a moment.",
            wdk_step_id=wdk_step_id,
            http_status=e.status,
        )
    return tool_error(
        ErrorCode.WDK_ERROR,
        f"VEuPathDB rejected request for step {wdk_step_id}: {e.detail}",
        wdk_step_id=wdk_step_id,
        http_status=e.status,
    )

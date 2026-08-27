"""The MCP servers this deployment admits, and the credential it presents."""

from __future__ import annotations

from assistant_core.mcp.admission import AdmissionRecord, AdmittedSources
from assistant_core.mcp.resolution import ToolSourceUnavailableError

from pathfinder.platform.config import get_settings

WDK_MCP_SOURCE_ID = "veupathdb-wdk-mcp"
WDK_MCP_PART_NAMESPACE = "wdk"

# The budget covers the longest call the served tools declare, so a control
# run is not cut off by the client.
WDK_MCP_CALL_SECONDS = 180


def admitted_tool_sources() -> AdmittedSources:
    """Every server this deployment admits.

    A server is admitted once its endpoint and the credential it takes are
    both configured, so a call never leaves without one.
    """
    settings = get_settings()
    endpoint = settings.pathfinder_wdk_mcp_url.strip()
    if not endpoint or not settings.pathfinder_wdk_mcp_token.strip():
        return AdmittedSources()
    return AdmittedSources(
        records=(
            AdmissionRecord(
                source_id=WDK_MCP_SOURCE_ID,
                endpoint=endpoint,
                credential_mode="service",
                part_namespace=WDK_MCP_PART_NAMESPACE,
                max_call_seconds=WDK_MCP_CALL_SECONDS,
            ),
        ),
    )


def source_credential(record: AdmissionRecord) -> str | None:
    """The credential this deployment presents to one admitted server."""
    if record.source_id != WDK_MCP_SOURCE_ID:
        msg = f"this deployment holds no credential for {record.source_id!r}"
        raise ToolSourceUnavailableError(msg)
    token = get_settings().pathfinder_wdk_mcp_token.strip()
    if not token:
        msg = (
            f"PATHFINDER_WDK_MCP_TOKEN must carry a credential "
            f"{record.source_id!r} accepts."
        )
        raise ToolSourceUnavailableError(msg)
    return token


__all__ = [
    "WDK_MCP_CALL_SECONDS",
    "WDK_MCP_PART_NAMESPACE",
    "WDK_MCP_SOURCE_ID",
    "admitted_tool_sources",
    "source_credential",
]

"""Typed payloads for Pathfinder's chat/SSE data-parts.

Each module defines the `DataChunk` payload for a specific `data-<name>`
stream part emitted by tools via `ToolReturn.metadata`. Models serialize
to camelCase JSON aliases matching the AI SDK / TypeScript wire format.
"""

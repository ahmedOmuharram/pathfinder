"""Export service — generates downloadable files, stores in Postgres with TTL."""

from __future__ import annotations

from assistant_core.platform.db import async_session_factory

from pathfinder.services.export.service import (
    ExportResult,
    ExportService,
    StoredExport,
)

__all__ = [
    "ExportResult",
    "ExportService",
    "StoredExport",
    "get_export_service",
]

_instance: ExportService | None = None


def get_export_service() -> ExportService:
    """Get the export service singleton (lazy init)."""
    global _instance  # noqa: PLW0603
    if _instance is None:
        _instance = ExportService(session_factory=async_session_factory)
    return _instance

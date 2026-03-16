"""Export service — generates downloadable files, stores in Redis with TTL."""

import threading

from veupath_chatbot.services.export.service import ExportResult, ExportService

__all__ = ["ExportResult", "ExportService", "get_export_service"]

_service: ExportService | None = None
_service_lock = threading.Lock()


def get_export_service() -> ExportService:
    """Get the export service singleton (lazy init)."""
    global _service
    if _service is not None:
        return _service
    with _service_lock:
        if _service is None:
            from veupath_chatbot.platform.redis import get_redis

            _service = ExportService(get_redis())
        return _service

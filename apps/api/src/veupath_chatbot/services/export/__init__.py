"""Export service — generates downloadable files, stores in Redis with TTL."""

import threading

from veupath_chatbot.platform.redis import get_redis
from veupath_chatbot.services.export.service import ExportResult, ExportService

__all__ = ["ExportResult", "ExportService", "get_export_service"]

_service_holder: dict[str, ExportService] = {}
_service_lock = threading.Lock()


def get_export_service() -> ExportService:
    """Get the export service singleton (lazy init)."""
    if "v" in _service_holder:
        return _service_holder["v"]
    with _service_lock:
        if "v" not in _service_holder:
            _service_holder["v"] = ExportService(get_redis())
        return _service_holder["v"]

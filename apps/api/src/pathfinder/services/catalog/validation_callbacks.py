"""Site-bound validation callbacks shared across agent + service paths.

Both ``ai/tools/standalone/strategy.py`` (agent path) and
``services/strategies/spec_build.py`` (declarative build path) call
:func:`pathfinder.services.catalog.param_validation.validate_parameters`
and need the same ``ValidationCallbacks`` shape.
"""

from __future__ import annotations

from collections.abc import Callable

from pathfinder.platform.errors import ValidationError
from pathfinder.platform.tool_errors import ToolErrorPayload
from pathfinder.services.catalog.param_validation import ValidationCallbacks
from pathfinder.services.catalog.record_type_resolution import (
    find_record_type_for_search,
    find_record_type_hint,
)


def make_validation_callbacks(
    site_id: str,
    *,
    error_payload: Callable[[ValidationError], ToolErrorPayload] | None = None,
) -> ValidationCallbacks:
    async def _resolve(
        record_type: str | None,
        search_name: str | None,
        *,
        require_match: bool = False,
        allow_fallback: bool = True,
    ) -> str | None:
        return await find_record_type_for_search(
            site_id,
            record_type,
            search_name,
            require_match=require_match,
            allow_fallback=allow_fallback,
        )

    async def _hint(search_name: str, exclude: str | None = None) -> str | None:
        return await find_record_type_hint(site_id, search_name, exclude)

    return ValidationCallbacks(
        resolve_record_type_for_search=_resolve,
        find_record_type_hint=_hint,
        validation_error_payload=error_payload,
    )

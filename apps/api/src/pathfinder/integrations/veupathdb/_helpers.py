"""Shared validation helpers for WDK integration clients."""

import contextlib

from pydantic import TypeAdapter, ValidationError

from pathfinder.platform.errors import WDKError
from pathfinder.platform.types import JSONValue


def _validate_list[T](raw: JSONValue, adapter: TypeAdapter[T]) -> list[T]:
    """Validate a JSON array into a typed list, skipping invalid items.

    Single ``isinstance(raw, list)`` guard is unavoidable since ``JSONValue``
    is a union.  Invalid items are silently skipped so one bad WDK entry
    does not crash the entire list.
    """
    if not isinstance(raw, list):
        msg = "Expected list response from WDK"
        raise WDKError(msg)
    results: list[T] = []
    for item in raw:
        with contextlib.suppress(ValidationError):
            results.append(adapter.validate_python(item))
    return results

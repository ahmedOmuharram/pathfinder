"""Parses Pydantic validation error text into structured items.

A tool-argument failure can arrive as Pydantic's human-readable text; the
parser turns it into machine-readable error payloads for the client.
"""

import re
from typing import cast

from assistant_core.platform.types import JSONArray, JSONObject
from pydantic import JsonValue

_HEADER_RE = re.compile(
    r"^\s*(?P<count>\d+)\s+validation error for\s+(?P<model>.+?)\s*$"
)


def _parse_meta(meta_str: str) -> dict[str, str]:
    """Parse ``key=value, key=value`` metadata from a Pydantic error line."""
    meta: dict[str, str] = {}
    for part in [p.strip() for p in meta_str.split(",")]:
        if not part or "=" not in part:
            continue
        key, value = part.split("=", 1)
        meta[key.strip()] = value.strip()
    return meta


def _parse_error_line(ln: str, current_loc: str) -> JSONObject:
    """Parse a single indented Pydantic error detail line into a structured dict."""
    detail = ln.strip()
    msg = detail
    meta: dict[str, str] = {}
    if "[" in detail and detail.endswith("]"):
        msg_part, meta_part = detail.split("[", 1)
        msg = msg_part.strip() or detail
        meta = _parse_meta(meta_part[:-1])

    err: JSONObject = {
        "loc": [current_loc],
        "msg": msg,
    }
    if meta.get("type"):
        err["type"] = meta["type"]
    if meta:
        err["meta"] = cast("JsonValue", meta)
    return err


def _collect_errors(lines: list[str]) -> JSONArray:
    """Walk body lines and collect structured error objects."""
    errors: JSONArray = []
    current_loc: str | None = None

    for ln in lines:
        if not ln.strip():
            continue
        if ln.startswith(" "):
            if current_loc is not None:
                errors.append(_parse_error_line(ln, current_loc))
        else:
            current_loc = ln.strip()
    return errors


def parse_pydantic_validation_error_text(text: str | None) -> JSONObject | None:
    """Parse Pydantic v2 ValidationError string into a structured payload.

    Returns a dict with keys:
    - model: string (best-effort)
    - errorCount: int | None
    - errors: list[dict] (best-effort)
    - raw: original text

    :param text: Pydantic error text (or None).
    :returns: Parsed validation summary or None.
    """
    if not text:
        return None
    if "validation error for" not in text:
        return None

    lines = [ln.rstrip("\n") for ln in str(text).splitlines()]
    header = next((ln for ln in lines if ln.strip()), "").strip()
    m = _HEADER_RE.match(header)
    if not m:
        return None

    model = (m.group("model") or "").strip() or None
    try:
        error_count: int | None = int(m.group("count"))
    except ValueError, TypeError:
        error_count = None

    return {
        "model": model,
        "errorCount": error_count,
        "errors": _collect_errors(lines[1:]),
        "raw": text,
    }

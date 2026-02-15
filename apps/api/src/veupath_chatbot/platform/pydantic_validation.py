"""Utilities for parsing Pydantic validation error text.

Some tool frameworks (including Kani) surface tool-argument validation failures as
plain text (Pydantic's human-readable format) rather than structured JSON. This
module provides a best-effort parser so we can return consistent, machine-readable
error payloads to the client.
"""

from __future__ import annotations

import re
from typing import cast

from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue

_HEADER_RE = re.compile(
    r"^\s*(?P<count>\d+)\s+validation error for\s+(?P<model>.+?)\s*$"
)


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
    except Exception:
        error_count = None

    errors: JSONArray = []
    current_loc: str | None = None

    def _parse_meta(meta_str: str) -> dict[str, str]:
        meta: dict[str, str] = {}
        for part in [p.strip() for p in meta_str.split(",")]:
            if not part or "=" not in part:
                continue
            key, value = part.split("=", 1)
            meta[key.strip()] = value.strip()
        return meta

    for ln in lines[1:]:
        if not ln.strip():
            continue
        # "loc" lines are unindented; details are indented.
        if ln.startswith(" "):
            if current_loc is None:
                continue
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
                type_val = meta.get("type")
                if isinstance(type_val, str):
                    err["type"] = type_val
            if meta:
                # dict[str, str] is a valid JSONValue (it's a dict[str, JSONValue])
                err["meta"] = cast(JSONValue, meta)
            errors.append(err)
        else:
            current_loc = ln.strip()

    return {
        "model": model,
        "errorCount": error_count,
        "errors": errors,
        "raw": text,
    }

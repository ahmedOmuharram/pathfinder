from __future__ import annotations

import secrets


def mint_note_id() -> str:
    """Short stable id for agent-references; caller handles uniqueness at DB."""
    return f"n-{secrets.token_hex(3)}"


def approx_body_tokens(body: str) -> int:
    """Char-based token approximation. Deterministic, stdlib-only.

    Scratchpad budget gating is coarse (10k ceiling); ±20% error is fine.
    Used for the ``body_tokens`` column written on insert/update.
    """
    return len(body) // 4

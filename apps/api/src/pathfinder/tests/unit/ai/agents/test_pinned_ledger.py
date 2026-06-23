"""Sub-agents read the Lead's ledger (curated structured state) via a pinned
instruction — so e.g. scoping sees what's already resolved and doesn't re-ask.
The Lead renders it into ``AgentDeps.ledger_summary``; the instruction surfaces
it (or nothing when empty)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from pathfinder.ai.agents._instructions import pinned_ledger


def _ctx(ledger_summary: str) -> Any:
    ctx = MagicMock()
    ctx.deps = MagicMock()
    ctx.deps.ledger_summary = ledger_summary
    return ctx


def test_pinned_ledger_renders_summary() -> None:
    rendered = pinned_ledger(
        _ctx("## Frame\n- present: True\n## Discovery\n- selected: 0")
    )
    assert rendered is not None
    assert "Frame" in rendered
    assert "Discovery" in rendered


def test_pinned_ledger_none_when_empty() -> None:
    assert pinned_ledger(_ctx("")) is None

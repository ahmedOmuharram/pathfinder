"""The discovery work order must carry a TARGETED RE-DISCOVERY directive when
the Lead re-dispatches discovery to find/replace a specific search after a plan
denial — so the discovery sub-agent keeps prior selections instead of starting
over (or worse, the Lead patching an existing step into a different search)."""

from __future__ import annotations

from pathfinder.ai.lead.sub_agent_dispatch import _discovery_work_order


def test_work_order_default_has_no_targeted_block() -> None:
    wo = _discovery_work_order(
        reason="initial discovery",
        intent_summary="find kinases",
        hints="",
        keep_prior_selections=False,
    )
    assert "TARGETED RE-DISCOVERY" not in wo
    assert "initial discovery" in wo
    assert "find kinases" in wo


def test_targeted_work_order_instructs_keep_and_replace() -> None:
    wo = _discovery_work_order(
        reason="plan denied: use GO not InterPro for kinases",
        intent_summary="find a GO molecular function kinase-activity search",
        hints="keep the signal-peptide search; replace the InterPro kinase step",
        keep_prior_selections=True,
    )
    assert "TARGETED RE-DISCOVERY" in wo
    assert "keep" in wo.lower()
    assert "find a GO molecular function kinase-activity search" in wo
    assert "keep the signal-peptide search; replace the InterPro kinase step" in wo


def test_hints_omitted_when_empty() -> None:
    wo = _discovery_work_order(
        reason="r",
        intent_summary="i",
        hints="",
        keep_prior_selections=False,
    )
    assert "Hints:" not in wo

"""The Ledger summary must shout when its build counts are known-stale.

The Lead quotes Ledger counts directly to the user. If the strategy was
edited outside the conversation, those counts are wrong and the summary is
the only place the Lead would notice.
"""

from pathfinder.ai.lead.ledger import (
    BuildSection,
    FrameSection,
    InvestigationLedger,
    VerificationSection,
)
from pathfinder.domain.strategy.staleness import StaleBuild


def _ledger(stale: StaleBuild | None) -> InvestigationLedger:
    return InvestigationLedger(
        user_intent=None,
        frame=FrameSection(),
        build=BuildSection(stale_build=stale),
        verification=VerificationSection(),
    )


def test_summary_has_no_stale_marker_when_fresh() -> None:
    assert "STALE" not in _ledger(None).render_summary()


def test_summary_flags_stale_build() -> None:
    stale = StaleBuild(changed_nodes=[("step_a", 2862, 587)])
    summary = _ledger(stale).render_summary()
    assert "STALE" in summary
    assert "2862" in summary
    assert "587" in summary


def test_stale_marker_names_the_live_read_tool() -> None:
    # The Lead needs to know what to do about it, not just that it happened.
    stale = StaleBuild(changed_nodes=[("step_a", 10, 11)])
    assert "get_live_strategy_state" in _ledger(stale).render_summary()


def test_build_section_defaults_to_fresh() -> None:
    assert BuildSection().stale_build is None

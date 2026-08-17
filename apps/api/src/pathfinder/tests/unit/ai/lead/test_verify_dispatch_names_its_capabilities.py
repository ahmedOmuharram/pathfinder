"""The Lead routes by tool description, so a capability it cannot name is lost.

Enrichment, control tests and record sampling run in the verification
sub-agent. A user asks for them directly. If the dispatch tool does not name
them, the Lead answers that the action is unavailable while the tool sits one
dispatch away.
"""

from __future__ import annotations

import pytest

from pathfinder.ai.lead import lead_agent
from pathfinder.ai.lead.sub_agent_dispatch import verify_strategy
from pathfinder.ai.tools.toolsets import verification

_DESCRIPTION = verify_strategy.__doc__ or ""

_USER_FACING = ["enrich", "control", "sample"]


class TestTheDispatchToolNamesWhatItCanDo:
    @pytest.mark.parametrize("capability", _USER_FACING)
    def test_a_capability_is_named(self, capability: str) -> None:
        assert capability in _DESCRIPTION.lower()

    def test_it_still_says_it_verifies(self) -> None:
        assert "verif" in _DESCRIPTION.lower()


class TestTheCapabilitiesAreReallyThere:
    def test_enrichment_belongs_to_the_verification_toolset(self) -> None:
        assert hasattr(verification, "run_gene_set_enrichment")

    def test_the_lead_does_not_carry_enrichment_itself(self) -> None:
        # If it ever does, the dispatch note above is the thing to correct.
        assert not hasattr(lead_agent, "run_gene_set_enrichment")

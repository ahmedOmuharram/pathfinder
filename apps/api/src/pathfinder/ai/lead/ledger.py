from __future__ import annotations

from assistant_core.graph.tool_summary import count_noun
from assistant_core.platform.pydantic_base import CamelModel
from pydantic import Field

from pathfinder.ai.graph.state import VerificationDigest
from pathfinder.ai.lead.intent import UserIntent
from pathfinder.ai.lead.ledger_render import (
    render_build_full,
    render_constraints_full,
    render_frame_full,
    render_verification_full,
)
from pathfinder.ai.lead.ledger_sections import (
    BuildSection,
    ConstraintSection,
    FrameSection,
    VerificationSection,
)


def build_contradiction(build: BuildSection, *, built_step_count: int) -> str | None:
    """Why a success verdict cannot stand over this build, or None.

    The ledger records what reached VEuPathDB. A digest may add detail to it
    and may never overrule it.
    """
    if build.outcome is None:
        if built_step_count:
            return None
        return "this turn built nothing and no step of the strategy is in VEuPathDB"
    if build.is_clean():
        return None
    return (
        f"the build pushed {count_noun(build.pushed_count, 'step')}, failed "
        f"{build.failed_count}, skipped {build.skipped_count} and left "
        f"{len(build.zero_result_steps)} empty"
    )


def digest_held_to_the_build(
    digest: VerificationDigest, contradiction: str
) -> VerificationDigest:
    """The digest with its verdict corrected to what the build supports."""
    return digest.model_copy(
        update={
            "success": False,
            "reason": f"Verification reported success, but {contradiction}.",
            "prose": (
                f"Verification cannot be reported: {contradiction}. "
                f"The checker's own account of the run follows.\n\n{digest.prose}"
            ),
            "caveats": [
                f"The verification verdict was refused: {contradiction}",
                *digest.caveats,
            ][:10],
        },
    )


class InvestigationLedger(CamelModel):
    """State of one investigation, read in full by the Lead each turn.

    Sub-agents receive scoped slices through typed work orders instead.
    The ledger is derived from pipeline state, not persisted.
    """

    user_intent: UserIntent | None
    frame: FrameSection
    build: BuildSection
    verification: VerificationSection
    constraints: ConstraintSection = Field(default_factory=ConstraintSection)

    def render_summary(self) -> str:
        """Render the compact markdown view the Lead reads in pinned context.

        It holds counts and derived booleans only, to keep the prompt bounded.
        """
        intent = self.user_intent
        intent_line = (
            f"- intent: {intent.classification.value} — {intent.inferred_goal[:120]}"
            if intent is not None
            else "- intent: not classified yet"
        )
        diff_line = (
            f"  differential: {intent.differential_sides}"
            if intent is not None
            and intent.is_differential
            and intent.differential_sides
            else ""
        )
        lines = ["# Investigation Ledger", intent_line]
        if diff_line:
            lines.append(diff_line)
        spec_diff = self.frame.spec_diff()
        lines.extend(
            [
                "",
                "## Frame",
                f"- present: {self.frame.present}",
                f"- criteria: {self.frame.criteria_count} "
                f"(bound: {self.frame.bound_count})",
                *(
                    [f"- this turn: {spec_diff.render()}"]
                    if spec_diff is not None
                    else []
                ),
                f"- dropped: {self.frame.dropped_count}",
                f"- open_slots: {self.frame.open_slot_count}",
                f"- needs_user: {self.frame.needs_user}",
                f"- ready_to_build: {self.frame.ready_to_build}",
                "",
                "## Build",
                *(
                    [self.build.stale_build.render()]
                    if self.build.stale_build is not None
                    else []
                ),
                f"- pushed: {self.build.pushed_count}",
                f"- failed: {self.build.failed_count}",
                f"- skipped: {self.build.skipped_count}",
                f"- zero_result_steps: {len(self.build.zero_result_steps)}",
                f"- needs_recovery: {self.build.needs_recovery}",
                f"- recovery_kind: {self.build.recovery_kind}",
                f"- succeeded: {self.build.succeeded}",
                "",
                "## Verification",
                f"- complete: {self.verification.complete}",
                f"- successful: {self.verification.successful}",
                "",
                "## Constraints",
                f"- blocking: {self.constraints.blocking}",
                f"- unmet (user-explicit): {self.constraints.unmet_count}",
                "### Stated by the user, oldest first",
                *(self.constraints.render_stated() or ["- (none)"]),
            ]
        )
        return "\n".join(lines)

    def render_section(self, section: str) -> str:
        """Render the full detail of one section."""
        if section == "frame":
            return render_frame_full(self.frame)
        if section == "build":
            return render_build_full(self.build)
        if section == "verification":
            return render_verification_full(self.verification)
        if section == "constraints":
            return render_constraints_full(self.constraints)
        msg = f"unknown section: {section}"
        raise ValueError(msg)

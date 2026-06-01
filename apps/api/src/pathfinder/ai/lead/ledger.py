from __future__ import annotations

from typing import Literal

from pydantic import Field, computed_field

from pathfinder.ai.agents.state import SearchOverview
from pathfinder.ai.graph.state import (
    ClarificationQuestion,
    ProblemFrame,
    VerificationDigest,
)
from pathfinder.ai.lead.deltas import OpenSlot
from pathfinder.ai.lead.intent import UserIntent
from pathfinder.domain.strategy.build_outcome import BuildOutcome
from pathfinder.domain.strategy.plan import StrategyPlan
from pathfinder.platform.pydantic_base import CamelModel

BlockedKind = Literal["none", "needs_discovery", "needs_user", "needs_approval"]
RecoveryKind = Literal[
    "none",
    "transient_retry",
    "param_replan",
    "search_replan",
    "user_clarify",
    "empty_result_review",
]
SubAgentName = Literal[
    "scope",
    "discover",
    "plan",
    "execute",
    "execute_recovery",
    "verify",
    "validate",
    "research",
]


class FrameSection(CamelModel):
    frame: ProblemFrame | None
    matches_current_intent: bool
    blocking_questions_unanswered: list[ClarificationQuestion] = Field(
        default_factory=list,
    )

    @computed_field
    def needed(self) -> bool:
        return self.frame is None or not self.matches_current_intent

    @computed_field
    def blocked(self) -> bool:
        return bool(self.blocking_questions_unanswered)


class SearchFitReport(CamelModel):
    """Per-search assessment: does its vocab cover the user's intent?"""

    search_name: str
    display_name: str
    selection_status: Literal["selected", "candidate", "rejected"]
    intent_sides_covered: dict[str, bool] = Field(default_factory=dict)
    intent_sides_unmatched: list[str] = Field(default_factory=list)
    confidence: float
    rationale: str = ""
    selection_reason: str = ""


class DiscoverySection(CamelModel):
    selections: dict[str, SearchOverview] = Field(default_factory=dict)
    fit_reports: list[SearchFitReport] = Field(default_factory=list)
    selected_count: int = 0
    rejected_count: int = 0
    intent_satisfied: bool = False
    intent_gap: str | None = None

    @computed_field
    def needs_more_discovery(self) -> bool:
        return self.selected_count == 0 or not self.intent_satisfied


class PlanSection(CamelModel):
    plan: StrategyPlan | None = None
    open_user_input_slots: list[OpenSlot] = Field(default_factory=list)
    open_discovery_slots: list[OpenSlot] = Field(default_factory=list)
    submitted_at_turn: str | None = None
    approved: bool = False
    last_denial_message: str | None = None

    @computed_field
    def ready_to_execute(self) -> bool:
        return (
            self.plan is not None
            and self.approved
            and not self.open_user_input_slots
            and not self.open_discovery_slots
        )

    @computed_field
    def blocked_kind(self) -> BlockedKind:
        if self.open_discovery_slots:
            return "needs_discovery"
        if self.open_user_input_slots:
            return "needs_user"
        if self.plan is not None and not self.approved:
            return "needs_approval"
        return "none"


class BuildSection(CamelModel):
    outcome: BuildOutcome | None = None
    pushed_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    zero_result_steps: list[str] = Field(default_factory=list)
    needs_recovery: bool = False
    recovery_kind: RecoveryKind = "none"

    @computed_field
    def succeeded(self) -> bool:
        return (
            self.outcome is not None
            and self.failed_count == 0
            and self.skipped_count == 0
            and not self.zero_result_steps
        )


class VerificationSection(CamelModel):
    digest: VerificationDigest | None = None

    @computed_field
    def complete(self) -> bool:
        return self.digest is not None

    @computed_field
    def successful(self) -> bool:
        return self.digest is not None and self.digest.success


class SubAgentCallRecord(CamelModel):
    sub_agent: SubAgentName
    called_at_turn: str
    input_summary: str
    output_summary: str
    succeeded: bool


class InvestigationLedger(CamelModel):
    """Lead reads this in full each turn. Sub-agents do NOT read it; they
    receive scoped slices via typed work orders.

    Constructed by ``InvestigationLedger.from_state`` (defined in
    ``derive.py``). The Ledger is derived, not persisted — only
    ``user_intent`` and ``last_build_outcome`` are added to ``PipelineState``;
    every other field of the Ledger composes from existing typed state.
    """

    user_intent: UserIntent | None
    frame: FrameSection
    discovery: DiscoverySection
    plan: PlanSection
    build: BuildSection
    verification: VerificationSection
    sub_agent_calls_this_turn: list[SubAgentCallRecord] = Field(
        default_factory=list,
    )
    sub_agent_calls_total: int = 0

    def render_summary(self) -> str:
        """Compact markdown view the Lead reads in pinned context.

        Counts + derived booleans + tiny samples. Full content of any
        section is fetched via ``read_ledger_section`` tool, keeping the
        Lead's prompt bounded for 20+-step strategies.
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
        lines.extend(
            [
                "",
                "## Frame",
                f"- needed: {self.frame.needed}",
                f"- blocked: {self.frame.blocked}",
                f"- blocking_questions: {len(self.frame.blocking_questions_unanswered)}",
                "",
                "## Discovery",
                f"- selected: {self.discovery.selected_count}",
                f"- rejected: {self.discovery.rejected_count}",
                f"- intent_satisfied: {self.discovery.intent_satisfied}",
                f"- intent_gap: {self.discovery.intent_gap or 'none'}",
                f"- needs_more_discovery: {self.discovery.needs_more_discovery}",
                "",
                "## Plan",
                f"- present: {self.plan.plan is not None}",
                f"- approved: {self.plan.approved}",
                f"- open_user_input_slots: {len(self.plan.open_user_input_slots)}",
                f"- open_discovery_slots: {len(self.plan.open_discovery_slots)}",
                f"- blocked_kind: {self.plan.blocked_kind}",
                f"- ready_to_execute: {self.plan.ready_to_execute}",
                "",
                "## Build",
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
                f"## Sub-agent calls this turn: {len(self.sub_agent_calls_this_turn)}",
            ]
        )
        return "\n".join(lines)

    def render_section(self, section: str) -> str:
        """Full detail of one section. Used by ``read_ledger_section`` tool."""
        if section == "frame":
            return _render_frame_full(self.frame)
        if section == "discovery":
            return _render_discovery_full(self.discovery)
        if section == "plan":
            return _render_plan_full(self.plan)
        if section == "build":
            return _render_build_full(self.build)
        if section == "verification":
            return _render_verification_full(self.verification)
        msg = f"unknown section: {section}"
        raise ValueError(msg)


def _render_frame_full(section: FrameSection) -> str:
    if section.frame is None:
        return "## Frame\n(no frame)"
    f = section.frame
    parts = [
        "## Frame (full)",
        f"- user_goal: {f.user_goal}",
        f"- interpreted_goal: {f.interpreted_goal}",
        f"- organism_scope: {f.organism_scope}",
        f"- record_type: {f.record_type}",
        f"- biological_entities: {f.biological_entities}",
        f"- inclusion_criteria: {f.inclusion_criteria}",
        f"- exclusion_criteria: {f.exclusion_criteria}",
        f"- success_criteria: {f.success_criteria}",
        f"- assumptions: {f.assumptions}",
        f"- ready_for_wdk_discovery: {f.ready_for_wdk_discovery}",
        f"- confidence: {f.confidence}",
    ]
    if section.blocking_questions_unanswered:
        parts.append("\n### Blocking questions")
        parts.extend(f"- {q.question}" for q in section.blocking_questions_unanswered)
    return "\n".join(parts)


def _render_discovery_full(section: DiscoverySection) -> str:
    parts = [
        "## Discovery (full)",
        f"- selected: {section.selected_count}, rejected: {section.rejected_count}",
    ]
    for status in ("selected", "candidate", "rejected"):
        group = [r for r in section.fit_reports if r.selection_status == status]
        if not group:
            continue
        parts.append(f"\n### {status.title()} ({len(group)})")
        for report in group:
            parts.extend(_render_fit_report(report))
    if section.intent_gap:
        parts.append(f"\nintent_gap: {section.intent_gap}")
    return "\n".join(parts)


def _render_fit_report(report: SearchFitReport) -> list[str]:
    out = [
        f"- `{report.search_name}` — {report.display_name} "
        f"(conf={report.confidence:.2f})",
    ]
    if report.selection_reason:
        out.append(f"    decision: {report.selection_reason}")
    if report.rationale:
        out.append(f"    why: {report.rationale}")
    if report.intent_sides_unmatched:
        out.append(f"    unmatched sides: {report.intent_sides_unmatched}")
    return out


def _render_plan_full(section: PlanSection) -> str:
    if section.plan is None:
        return "## Plan\n(no plan yet)"
    plan = section.plan
    parts = [
        "## Plan (full)",
        f"- id: {plan.id}",
        f"- title: {plan.title}",
        f"- status: {plan.status.value}",
        f"- step_count: {len(plan.steps)}",
        f"- connection_count: {len(plan.connections)}",
    ]
    for step in plan.steps:
        parts.append(
            f"- step {step.id} ({step.step_type.value}) "
            f"search={step.search_name} status={step.status.value}",
        )
        parts.extend(
            f"    {p.name}={p.value!r} status={p.status.value} required={p.required}"
            for p in step.parameters
        )
    if section.open_user_input_slots:
        parts.append("\n### Open user-input slots")
        parts.extend(
            f"- {s.step_id}.{s.param_name}: {s.question}"
            for s in section.open_user_input_slots
        )
    if section.open_discovery_slots:
        parts.append("\n### Open discovery slots")
        parts.extend(
            f"- {s.step_id}.{s.param_name}" for s in section.open_discovery_slots
        )
    return "\n".join(parts)


def _render_build_full(section: BuildSection) -> str:
    if section.outcome is None:
        return "## Build\n(no build yet)"
    o = section.outcome
    parts = [
        "## Build (full)",
        f"- pushed: {len(o.pushed_step_ids)}",
        f"- failed: {len(o.failed_steps)}",
        f"- skipped: {len(o.skipped_step_ids)}",
        f"- zero_result_steps: {o.zero_step_ids}",
        f"- wdk_strategy_id: {o.wdk_strategy_id}",
        f"- root_count: {o.root_count}",
    ]
    if o.failed_steps:
        parts.append("\n### Failed steps")
        parts.extend(
            f"- {f.step_id} ({f.search_name}): {f.error}" for f in o.failed_steps
        )
    return "\n".join(parts)


def _render_verification_full(section: VerificationSection) -> str:
    if section.digest is None:
        return "## Verification\n(not run yet)"
    d = section.digest
    parts = [
        "## Verification (full)",
        f"- success: {d.success}",
        f"- prose: {d.prose}",
    ]
    if d.key_findings:
        parts.append("\n### Key findings")
        parts.extend(f"- {kf}" for kf in d.key_findings)
    if d.caveats:
        parts.append("\n### Caveats")
        parts.extend(f"- {c}" for c in d.caveats)
    return "\n".join(parts)

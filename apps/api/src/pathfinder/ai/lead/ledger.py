from __future__ import annotations

from typing import Literal

from pydantic import Field, computed_field

from pathfinder.ai.graph.state import VerificationDigest
from pathfinder.ai.lead.intent import UserIntent
from pathfinder.domain.parameters.values import (
    MultiPickValue,
    ParamValue,
    SinglePickValue,
    to_wire,
)
from pathfinder.domain.strategy.build_outcome import BuildOutcome, NodeResult
from pathfinder.domain.strategy.constraints import GroundedConstraint, is_blocking
from pathfinder.domain.strategy.operational_spec import (
    Criterion,
    OperationalSpec,
    StructureNode,
)
from pathfinder.domain.strategy.staleness import StaleBuild
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.services.catalog.param_intent import (
    contrast_role_of,
    is_direction_param,
)

RecoveryKind = Literal[
    "none",
    "transient_retry",
    "param_replan",
    "search_replan",
    "user_clarify",
    "empty_result_review",
]
SubAgentName = Literal[
    "frame",
    "build",
    "execute_recovery",
    "verify",
    "validate",
    "research",
]


class ContrastSummary(CamelModel):
    """Which way a differential criterion points.

    WDK computes fold change as comparator against reference. A swap of the two
    inverts the biology and still returns a plausible gene set.
    """

    criterion_id: str
    comparator: str | None = None
    reference: str | None = None
    direction: str | None = None

    @computed_field
    def summary(self) -> str:
        subject = self.comparator or "(unset)"
        baseline = self.reference or "(unset)"
        lead = f"{self.direction} in " if self.direction else ""
        return f"{lead}{subject} vs {baseline}"


def _contrast_for(crit: Criterion) -> ContrastSummary | None:
    comparator: str | None = None
    reference: str | None = None
    direction: str | None = None
    for name, value in crit.resolved_params.items():
        role = contrast_role_of(name)
        if role == "comparison":
            comparator = _plain_value(value)
        elif role == "reference":
            reference = _plain_value(value)
        elif is_direction_param(name):
            direction = _plain_value(value)
    if comparator is None and reference is None:
        return None
    return ContrastSummary(
        criterion_id=crit.id,
        comparator=comparator,
        reference=reference,
        direction=direction,
    )


def _plain_value(value: ParamValue) -> str:
    """Return a vocabulary term in readable form instead of its JSON wire form."""
    if isinstance(value, MultiPickValue):
        return ", ".join(value.values)
    if isinstance(value, SinglePickValue):
        return value.value
    return to_wire(value)


class FrameSection(CamelModel):
    """The OperationalSpec the FRAME phase produced.

    It holds criteria bound to WDK searches with resolved params and a
    combine structure.
    """

    spec: OperationalSpec | None = None

    @computed_field
    def present(self) -> bool:
        return self.spec is not None

    @computed_field
    def criteria_count(self) -> int:
        return len(self.spec.criteria) if self.spec else 0

    @computed_field
    def bound_count(self) -> int:
        return sum(1 for c in self.spec.criteria if c.bound) if self.spec else 0

    @computed_field
    def open_slot_count(self) -> int:
        if self.spec is None:
            return 0
        return len(self.spec.open_slots) + sum(
            len(c.open_params) for c in self.spec.criteria
        )

    @computed_field
    def dropped_count(self) -> int:
        return len(self.spec.dropped) if self.spec else 0

    @computed_field
    def ready_to_build(self) -> bool:
        return self.spec.ready_to_build if self.spec else False

    @computed_field
    def needs_user(self) -> bool:
        if self.spec is None:
            return False
        return bool(self.spec.open_slots) or any(
            c.open_params for c in self.spec.criteria
        )

    @computed_field
    def contrasts(self) -> list[ContrastSummary]:
        """One entry per criterion that contrasts two sample groups."""
        if self.spec is None:
            return []
        found = (_contrast_for(c) for c in self.spec.criteria)
        return [c for c in found if c is not None]

    @computed_field
    def structure_render(self) -> str | None:
        """Compact combine-tree string for the UI."""
        if self.spec is None or self.spec.structure is None:
            return None
        return _render_structure(self.spec.structure.root, self.spec)


class BuildSection(CamelModel):
    outcome: BuildOutcome | None = None
    # Set when a live read shows the strategy changed since this build.
    stale_build: StaleBuild | None = None
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

    @computed_field
    def node_results(self) -> list[NodeResult]:
        """Per-node build detail for the UI."""
        return list(self.outcome.node_results) if self.outcome else []

    @computed_field
    def wdk_strategy_id(self) -> int | None:
        return self.outcome.wdk_strategy_id if self.outcome else None

    @computed_field
    def wdk_url(self) -> str | None:
        return self.outcome.wdk_url if self.outcome else None


class VerificationSection(CamelModel):
    digest: VerificationDigest | None = None

    @computed_field
    def complete(self) -> bool:
        return self.digest is not None

    @computed_field
    def successful(self) -> bool:
        return self.digest is not None and self.digest.success


class ConstraintSection(CamelModel):
    grounded: list[GroundedConstraint] = Field(default_factory=list)

    @computed_field
    def unmet_count(self) -> int:
        return sum(1 for g in self.grounded if is_blocking(g))

    @computed_field
    def blocking(self) -> bool:
        return any(is_blocking(g) for g in self.grounded)


class SubAgentCallRecord(CamelModel):
    sub_agent: SubAgentName
    called_at_turn: str
    input_summary: str
    output_summary: str
    succeeded: bool


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
    sub_agent_calls_this_turn: list[SubAgentCallRecord] = Field(
        default_factory=list,
    )
    sub_agent_calls_total: int = 0

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
        lines.extend(
            [
                "",
                "## Frame",
                f"- present: {self.frame.present}",
                f"- criteria: {self.frame.criteria_count} "
                f"(bound: {self.frame.bound_count})",
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
                "",
                f"## Sub-agent calls this turn: {len(self.sub_agent_calls_this_turn)}",
            ]
        )
        return "\n".join(lines)

    def render_section(self, section: str) -> str:
        """Render the full detail of one section."""
        if section == "frame":
            return _render_frame_full(self.frame)
        if section == "build":
            return _render_build_full(self.build)
        if section == "verification":
            return _render_verification_full(self.verification)
        if section == "constraints":
            return _render_constraints_full(self.constraints)
        msg = f"unknown section: {section}"
        raise ValueError(msg)


def _render_constraints_full(section: ConstraintSection) -> str:
    if not section.grounded:
        return "## Constraints\n(none)"
    lines = [
        "## Constraints",
        f"blocking: {section.blocking}  unmet (user-explicit): {section.unmet_count}",
    ]
    for g in section.grounded:
        c = g.constraint
        realized = g.realized_value or "—"
        note = f" — {g.note}" if g.note else ""
        lines.append(
            f"- [{c.source}] {c.label} ({c.kind}): requested {c.requested_value!r} "
            f"→ {g.status} (realized {realized}){note}"
        )
    return "\n".join(lines)


def _render_frame_full(section: FrameSection) -> str:
    spec = section.spec
    if spec is None:
        return "## Frame\n(no spec yet)"
    parts = [
        "## Frame (full)",
        f"- goal: {spec.goal}",
        f"- interpreted_goal: {spec.interpreted_goal}",
        f"- record_type: {spec.record_type}",
        f"- organism_scope: {spec.organism_scope or 'any'}",
        f"- title: {spec.title}",
        f"- ready_to_build: {spec.ready_to_build}",
        "",
        f"### Criteria ({len(spec.criteria)})",
    ]
    for crit in spec.criteria:
        parts.extend(_render_criterion(crit))
    if spec.structure is not None:
        parts.append("\n### Structure")
        parts.append(_render_structure(spec.structure.root, spec))
    if spec.open_slots:
        parts.append("\n### Open slots (user must answer)")
        parts.extend(
            f"- {s.criterion_id or '—'}.{s.param_name}: {s.question}"
            for s in spec.open_slots
        )
    if spec.dropped:
        parts.append("\n### Dropped criteria")
        parts.extend(f"- {d.text} — {d.reason}" for d in spec.dropped)
    return "\n".join(parts)


def _render_criterion(crit: Criterion) -> list[str]:
    out = [
        f"- `{crit.id}` [{crit.role}] {crit.text} → "
        f"search={crit.search_name or '(unbound)'} (conf={crit.confidence:.2f})",
    ]
    out.extend(f"    {name}={value!r}" for name, value in crit.resolved_params.items())
    out.extend(f"    OPEN {s.param_name}: {s.question}" for s in crit.open_params)
    return out


def _render_structure(node: StructureNode, spec: OperationalSpec) -> str:
    by_id = {c.id: c for c in spec.criteria}
    if node.kind in {"leaf", "transform"}:
        crit = by_id.get(node.criterion_id or "")
        name = (
            crit.search_name
            if crit and crit.search_name
            else (node.criterion_id or "?")
        )
        if node.kind == "transform":
            inner = _render_structure(node.inputs[0], spec) if node.inputs else "?"
            return f"{name}({inner})"
        return name
    op = node.operator.value if node.operator else "?"
    inner = f" {op} ".join(_render_structure(child, spec) for child in node.inputs)
    return f"({inner})"


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

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from pathfinder.devtools.models import (
    Anomaly,
    CapturedToolCall,
    DecisionArgs,
    LedgerConstraintsProbe,
    RunSummary,
    SearchArgs,
)

LOOP_THRESHOLD = 5
BUDGET_WARN_TOKENS = 200_000
SERVICE_ERROR_THRESHOLD = 2

_SERVICE_ERROR_RE = re.compile(
    r"5\d\d (?:internal server error|server error)|server error '5|"
    r"temporarily unavailable",
    re.IGNORECASE,
)
_OUTAGE_REASON_RE = re.compile(
    r"server error|service (?:unavail|error)|unavailable|5\d\d|temporarily",
    re.IGNORECASE,
)


def _evidence(calls: list[CapturedToolCall]) -> list[str]:
    return [f"tools/{c.seq:02d}-{c.tool}.json" for c in calls]


def _catch_22(calls: list[CapturedToolCall]) -> list[Anomaly]:
    missing: dict[tuple[str | None, str | None], list[CapturedToolCall]] = defaultdict(
        list
    )
    unknown: dict[tuple[str | None, str | None], list[CapturedToolCall]] = defaultdict(
        list
    )
    for call in calls:
        for err in call.errors:
            key = (err.search_name, err.param)
            if err.kind == "missing_required":
                missing[key].append(call)
            elif err.kind == "unknown_param":
                unknown[key].append(call)
    out: list[Anomaly] = []
    for key in sorted(
        set(missing) & set(unknown), key=lambda k: (k[0] or "", k[1] or "")
    ):
        search, param = key
        evidence_calls = missing[key] + unknown[key]
        where = f" on {search!r}" if search else ""
        out.append(
            Anomaly(
                kind="validation_catch_22",
                severity="critical",
                message=(
                    f"Parameter {param!r}{where} is required by one validator but "
                    f"rejected as unknown by another — unsatisfiable. The planner "
                    f"cannot produce any value that passes both."
                ),
                evidence=_evidence(evidence_calls),
                details={"param": param, "search_name": search},
            )
        )
    return out


def _loops(calls: list[CapturedToolCall]) -> list[Anomaly]:
    by_tool: dict[str, list[CapturedToolCall]] = defaultdict(list)
    for call in calls:
        if call.status == "failed":
            by_tool[call.tool].append(call)
    out: list[Anomaly] = []
    for tool, failed in sorted(by_tool.items()):
        if len(failed) >= LOOP_THRESHOLD:
            signatures = {(e.kind, e.param) for c in failed for e in c.errors}
            out.append(
                Anomaly(
                    kind="loop",
                    severity="critical",
                    message=(
                        f"{tool} failed {len(failed)} times "
                        f"({len(signatures) or 'unclassified'} distinct error signatures) "
                        f"— the agent is stuck retrying."
                    ),
                    evidence=_evidence(failed),
                    details={"tool": tool, "failures": len(failed)},
                )
            )
    return out


def _wdk_service_errors(calls: list[CapturedToolCall]) -> list[Anomaly]:
    by_search: dict[tuple[str, str | None], list[CapturedToolCall]] = defaultdict(list)
    for call in calls:
        if call.status != "failed" or not call.result:
            continue
        if "SEARCH_UNAVAILABLE" in call.result:
            continue
        if not _SERVICE_ERROR_RE.search(call.result):
            continue
        search = SearchArgs.model_validate(call.args or {}).search_name
        by_search[(call.tool, search)].append(call)
    out: list[Anomaly] = []
    for (tool, search), hits in sorted(
        by_search.items(), key=lambda kv: (kv[0][0], kv[0][1] or "")
    ):
        if len(hits) < SERVICE_ERROR_THRESHOLD:
            continue
        where = f" on {search!r}" if search else ""
        out.append(
            Anomaly(
                kind="wdk_service_error",
                severity="warning",
                message=(
                    f"{tool} hit a WDK server error (5xx){where} {len(hits)} times "
                    f"— the agent retried an unavailable search instead of routing "
                    f"around it. Likely an upstream outage, not a PathFinder bug."
                ),
                evidence=_evidence(hits),
                details={"tool": tool, "search_name": search, "count": len(hits)},
            )
        )
    return out


def _outage_driven_rejection(calls: list[CapturedToolCall]) -> list[Anomaly]:
    out: list[Anomaly] = []
    for call in calls:
        if call.tool != "update_search_decision" or call.status != "completed":
            continue
        decision = DecisionArgs.model_validate(call.args or {})
        if decision.selection_status != "rejected":
            continue
        if not _OUTAGE_REASON_RE.search(
            f"{decision.rationale} {decision.selection_reason}"
        ):
            continue
        where = f" {decision.search_name!r}" if decision.search_name else ""
        out.append(
            Anomaly(
                kind="outage_driven_rejection",
                severity="warning",
                message=(
                    f"Search{where} was rejected for a service-outage reason, not a "
                    f"scientific one — the plan silently drops a data dimension the "
                    f"user asked for, yet the turn still reports success. Re-run when "
                    f"WDK recovers."
                ),
                evidence=_evidence([call]),
                details={"search_name": decision.search_name},
            )
        )
    return out


def _silent_constraint_violation(
    ledgers: dict[str, dict[str, Any]],
) -> list[Anomaly]:
    out: list[Anomaly] = []
    for phase, ledger in ledgers.items():
        raw = (ledger or {}).get("constraints")
        if raw is None:
            continue
        probe = LedgerConstraintsProbe.model_validate(raw)
        if not probe.blocking:
            continue
        labels = [
            g.constraint.label
            for g in probe.grounded
            if g.constraint.source == "user_explicit"
            and g.status in {"substituted", "ungroundable"}
        ]
        out.append(
            Anomaly(
                kind="silent_constraint_violation",
                severity="critical",
                message=(
                    f"{probe.unmet_count} user-explicit constraint(s) unmet "
                    f"({', '.join(labels) or 'unnamed'}) yet the turn did not pause "
                    f"or flag it — the plan silently deviated from what the user asked."
                ),
                evidence=[f"state/{phase}.json"],
                details={
                    "phase": phase,
                    "unmet_count": probe.unmet_count,
                    "labels": labels,
                },
            )
        )
    return out


def _silent_zero(ledgers: dict[str, dict[str, Any]]) -> list[Anomaly]:
    out: list[Anomaly] = []
    for phase, ledger in ledgers.items():
        zero_steps = ((ledger or {}).get("build") or {}).get("zeroResultSteps") or []
        if zero_steps:
            out.append(
                Anomaly(
                    kind="silent_zero",
                    severity="warning",
                    message=(
                        f"{len(zero_steps)} step(s) returned 0 results in {phase} "
                        f"({', '.join(map(str, zero_steps))}) — possible silent failure "
                        f"(e.g. missing JSESSIONID, wrong params)."
                    ),
                    evidence=[f"state/{phase}.json"],
                    details={"phase": phase, "zero_result_steps": zero_steps},
                )
            )
    return out


def _budget(summary: RunSummary) -> list[Anomaly]:
    if summary.tokens < BUDGET_WARN_TOKENS:
        return []
    severity = "critical" if summary.status == "error" else "warning"
    return [
        Anomaly(
            kind="budget_burn",
            severity=severity,
            message=(
                f"Turn consumed {summary.tokens} tokens (${summary.cost_usd:.2f}) "
                f"with status={summary.status} — abnormally high."
            ),
            evidence=["summary.json"],
            details={"tokens": summary.tokens, "cost_usd": summary.cost_usd},
        )
    ]


def _no_plan(summary: RunSummary) -> list[Anomaly]:
    if summary.terminal_error and "no plan" in summary.terminal_error.lower():
        return [
            Anomaly(
                kind="no_plan",
                severity="critical",
                message=f"Planning terminated without a plan: {summary.terminal_error}",
                evidence=["summary.json", "state/planning.json"],
                details={"terminal_error": summary.terminal_error},
            )
        ]
    return []


def diagnose(
    calls: list[CapturedToolCall],
    ledgers: dict[str, dict[str, Any]],
    summary: RunSummary,
) -> list[Anomaly]:
    """Run every fingerprint detector over a captured run and return the
    anomalies found, most severe first. Pure; never raises."""

    anomalies = (
        _catch_22(calls)
        + _loops(calls)
        + _wdk_service_errors(calls)
        + _outage_driven_rejection(calls)
        + _silent_constraint_violation(ledgers)
        + _silent_zero(ledgers)
        + _budget(summary)
        + _no_plan(summary)
    )
    rank = {"critical": 0, "warning": 1, "info": 2}
    return sorted(anomalies, key=lambda a: rank.get(a.severity, 3))

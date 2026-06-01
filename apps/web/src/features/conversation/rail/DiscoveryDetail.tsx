"use client";

import type {
  LedgerDiscoveryPayload,
  LedgerSearchFitReport,
} from "@pathfinder/shared";

import { StatusPill, type Tone } from "./LedgerPanelPrimitives";

const STATUS_TONE: Record<LedgerSearchFitReport["selectionStatus"], Tone> = {
  selected: "good",
  candidate: "warn",
  rejected: "bad",
};

const STATUS_ORDER: LedgerSearchFitReport["selectionStatus"][] = [
  "selected",
  "candidate",
  "rejected",
];

export function DiscoveryDetail({
  discovery,
}: {
  discovery: LedgerDiscoveryPayload;
}) {
  const reports = discovery.fitReports;
  if (reports.length === 0) {
    return (
      <p className="px-4 py-3 text-xs text-muted-foreground">
        No searches inspected yet. Discovery hasn&apos;t committed a decision.
      </p>
    );
  }
  return (
    <div className="space-y-4 px-4 py-3">
      {discovery.intentGap !== null && discovery.intentGap !== "" && (
        <p className="rounded border border-amber-500/40 bg-amber-500/5 px-2 py-1.5 text-[11px] italic text-amber-700 dark:text-amber-300">
          intent gap: {discovery.intentGap}
        </p>
      )}
      {STATUS_ORDER.map((status) => {
        const group = reports.filter((r) => r.selectionStatus === status);
        if (group.length === 0) return null;
        return (
          <section key={status}>
            <h4 className="mb-1.5 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
              {status}
              <span className="font-mono text-[10px] text-foreground">
                ({group.length})
              </span>
            </h4>
            <div className="space-y-2">
              {group.map((report) => (
                <SearchDecisionCard key={report.searchName} report={report} />
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}

function SearchDecisionCard({ report }: { report: LedgerSearchFitReport }) {
  const confidencePct = Math.round(report.confidence * 100);
  return (
    <article className="rounded border border-border bg-card px-2.5 py-2 text-xs">
      <header className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="truncate font-medium text-foreground">
            {report.displayName}
          </div>
          <code className="text-[10px] text-muted-foreground">
            {report.searchName}
          </code>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <StatusPill
            text={`${confidencePct}%`}
            tone={STATUS_TONE[report.selectionStatus]}
          />
        </div>
      </header>
      {report.selectionReason !== "" && (
        <div className="mt-1.5">
          <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            decision
          </span>
          <p className="mt-0.5 leading-snug text-foreground">
            {report.selectionReason}
          </p>
        </div>
      )}
      {report.rationale !== "" && (
        <div className="mt-1.5">
          <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            why
          </span>
          <p className="mt-0.5 leading-snug text-muted-foreground">
            {report.rationale}
          </p>
        </div>
      )}
      {report.intentSidesUnmatched.length > 0 && (
        <div className="mt-1.5 flex flex-wrap items-center gap-1">
          <span className="text-[10px] text-muted-foreground">
            sides unmatched:
          </span>
          {report.intentSidesUnmatched.map((side) => (
            <StatusPill key={side} text={side} tone="warn" />
          ))}
        </div>
      )}
    </article>
  );
}

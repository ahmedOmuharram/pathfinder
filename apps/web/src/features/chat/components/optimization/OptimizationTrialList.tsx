import { useState } from "react";
import type { OptimizationTrial } from "@pathfinder/shared";
import { ChevronDown, ChevronRight } from "lucide-react";
import {
  pct,
  fmt,
} from "@/features/chat/components/optimization/optimizationFormatters";

function TrialTable({
  trials,
  paramNames,
  paretoTrialNumbers,
}: {
  trials: OptimizationTrial[];
  paramNames: string[];
  paretoTrialNumbers?: Set<number>;
}) {
  if (trials.length === 0) return null;

  const hasPositiveHits = trials.some((t) => t.positiveHits != null);
  const hasNegativeHits = trials.some((t) => t.negativeHits != null);

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-xs">
        <thead>
          <tr className="border-b border-border text-xs uppercase tracking-wider text-muted-foreground">
            <th className="px-1.5 py-1">#</th>
            {paramNames.map((n) => (
              <th key={n} className="px-1.5 py-1 font-medium">
                {n}
              </th>
            ))}
            <th className="px-1.5 py-1">Score</th>
            <th className="px-1.5 py-1">Recall</th>
            <th className="px-1.5 py-1">FPR</th>
            {hasPositiveHits && <th className="px-1.5 py-1">+Hits</th>}
            {hasNegativeHits && <th className="px-1.5 py-1">-Hits</th>}
            <th className="px-1.5 py-1">Results</th>
          </tr>
        </thead>
        <tbody>
          {trials.map((t) => {
            const isPareto = paretoTrialNumbers?.has(t.trialNumber);
            return (
              <tr
                key={t.trialNumber}
                className={`border-b border-border last:border-0 ${isPareto ? "bg-primary/5" : ""}`}
              >
                <td className="px-1.5 py-1 tabular-nums text-muted-foreground">
                  {t.trialNumber}
                </td>
                {paramNames.map((n) => (
                  <td key={n} className="px-1.5 py-1 tabular-nums">
                    {fmt(
                      typeof t.parameters[n] === "number"
                        ? (t.parameters[n] as number)
                        : null,
                      3,
                    ) === "--"
                      ? String(t.parameters[n] ?? "--")
                      : fmt(t.parameters[n] as number, 3)}
                  </td>
                ))}
                <td className="px-1.5 py-1 tabular-nums font-medium">
                  {fmt(t.score, 4)}
                </td>
                <td className="px-1.5 py-1 tabular-nums">{pct(t.recall)}</td>
                <td className="px-1.5 py-1 tabular-nums">{pct(t.falsePositiveRate)}</td>
                {hasPositiveHits && (
                  <td className="px-1.5 py-1 tabular-nums">
                    {t.positiveHits != null
                      ? `${t.positiveHits}/${t.totalPositives ?? "?"}`
                      : "--"}
                  </td>
                )}
                {hasNegativeHits && (
                  <td className="px-1.5 py-1 tabular-nums">
                    {t.negativeHits != null
                      ? `${t.negativeHits}/${t.totalNegatives ?? "?"}`
                      : "--"}
                  </td>
                )}
                <td className="px-1.5 py-1 tabular-nums">{t.resultCount ?? "--"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function CollapsibleTrialSection({
  displayTrials,
  allTrialsCount,
  recentTrialsCount,
  paramNames,
  paretoTrialNumbers,
}: {
  displayTrials: OptimizationTrial[];
  allTrialsCount: number;
  recentTrialsCount: number;
  paramNames: string[];
  paretoTrialNumbers: Set<number>;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div>
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="mb-1 flex w-full items-center gap-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground transition-colors duration-150 hover:text-foreground"
      >
        {expanded ? (
          <ChevronDown className="h-3 w-3" />
        ) : (
          <ChevronRight className="h-3 w-3" />
        )}
        <span>Recent trials</span>
        {allTrialsCount > recentTrialsCount ? (
          <span className="ml-auto font-normal normal-case tracking-normal text-muted-foreground">
            Showing last {recentTrialsCount} of {allTrialsCount} trials
          </span>
        ) : null}
      </button>
      {expanded && (
        <TrialTable
          trials={displayTrials}
          paramNames={paramNames}
          paretoTrialNumbers={paretoTrialNumbers}
        />
      )}
    </div>
  );
}

import type { ScoredComparison } from "@pathfinder/shared";
import { Trophy } from "lucide-react";

function fmt(value: number | null | undefined): string {
  return value == null ? "—" : value.toFixed(2);
}

export function DataScoredComparison({ data }: { data: ScoredComparison }) {
  return (
    <div
      data-testid="data-scored-comparison"
      className="my-2 rounded-md border border-border bg-card px-3 py-2 text-xs"
    >
      <div className="flex items-center gap-2">
        <Trophy className="size-3.5 text-muted-foreground" aria-hidden />
        <span className="text-sm font-medium">Scored comparison</span>
        <span className="ml-auto text-[10px] uppercase tracking-wide text-muted-foreground">
          ranked by {data.objective}
        </span>
      </div>

      <ul className="mt-2 space-y-1.5">
        {data.variants.map((v) => {
          const isWinner = data.winnerLabel != null && v.label === data.winnerLabel;
          const failed = v.error != null && v.error !== "";
          return (
            <li
              key={v.label}
              className={`rounded-md border p-2 ${
                isWinner
                  ? "border-primary/60 bg-primary/5"
                  : "border-border/60 bg-muted/20"
              }`}
            >
              <div className="flex items-baseline gap-2">
                <span className="font-medium text-foreground">{v.label}</span>
                {isWinner && (
                  <span className="rounded bg-primary/15 px-1 text-[10px] font-medium text-primary">
                    winner
                  </span>
                )}
                <span className="ml-auto font-mono text-[11px] text-foreground">
                  {failed ? "—" : `MCC ${fmt(v.mcc)}`}
                </span>
              </div>
              {failed ? (
                <div className="mt-0.5 text-[11px] text-destructive">
                  failed: {v.error}
                </div>
              ) : (
                <div className="mt-0.5 font-mono text-[11px] text-muted-foreground">
                  F1 {fmt(v.f1)} · prec {fmt(v.precision)} · sens {fmt(v.sensitivity)} ·
                  bal-acc {fmt(v.balancedAccuracy)}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

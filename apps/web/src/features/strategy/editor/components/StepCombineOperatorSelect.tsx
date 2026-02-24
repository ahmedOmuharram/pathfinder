"use client";

import type { ColocationParams } from "@pathfinder/shared";
import { CombineOperator, CombineOperatorLabels } from "@pathfinder/shared";
import { OpBadge } from "@/features/strategy/graph/components/OpBadge";

type StepCombineOperatorSelectProps = {
  operatorValue: string;
  onOperatorChange: (nextValue: string) => void;
  colocationParams?: ColocationParams;
  onColocationParamsChange: (nextValue: ColocationParams) => void;
};

const COMBINE_OPERATORS = Object.values(CombineOperator);

export function StepCombineOperatorSelect({
  operatorValue,
  onOperatorChange,
  colocationParams,
  onColocationParamsChange,
}: StepCombineOperatorSelectProps) {
  const showColocate = operatorValue === "COLOCATE";
  return (
    <div>
      <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Operator
      </label>
      <div className="grid grid-cols-2 gap-2">
        {COMBINE_OPERATORS.map((op) => {
          const selected = op === operatorValue;
          return (
            <button
              key={op}
              type="button"
              onClick={() => onOperatorChange(op)}
              className={`flex items-center justify-between rounded-md border px-3 py-2 text-left transition-colors duration-150 ${
                selected
                  ? "border-foreground bg-card"
                  : "border-border bg-card hover:border-input"
              }`}
            >
              <div className="flex flex-col">
                <div className="flex items-center gap-2">
                  <OpBadge operator={op} size="sm" />
                  <span className="text-sm font-semibold text-foreground">
                    {CombineOperatorLabels[op]}
                  </span>
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {showColocate && (
        <div className="mt-3 space-y-2 rounded-md border border-border bg-card p-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Colocation parameters
          </div>
          <div className="grid grid-cols-2 gap-2">
            <label className="text-sm text-foreground">
              <div className="mb-1 text-xs text-muted-foreground">Upstream (bp)</div>
              <input
                type="number"
                min={0}
                value={colocationParams?.upstream ?? 0}
                onChange={(e) =>
                  onColocationParamsChange({
                    upstream: Math.max(0, Number(e.target.value || 0)),
                    downstream: colocationParams?.downstream ?? 0,
                    strand: colocationParams?.strand ?? "both",
                  })
                }
                className="w-full rounded-md border border-border bg-card px-3 py-2 text-sm text-foreground"
              />
            </label>
            <label className="text-sm text-foreground">
              <div className="mb-1 text-xs text-muted-foreground">Downstream (bp)</div>
              <input
                type="number"
                min={0}
                value={colocationParams?.downstream ?? 0}
                onChange={(e) =>
                  onColocationParamsChange({
                    upstream: colocationParams?.upstream ?? 0,
                    downstream: Math.max(0, Number(e.target.value || 0)),
                    strand: colocationParams?.strand ?? "both",
                  })
                }
                className="w-full rounded-md border border-border bg-card px-3 py-2 text-sm text-foreground"
              />
            </label>
          </div>
          <label className="text-sm text-foreground">
            <div className="mb-1 text-xs text-muted-foreground">Strand</div>
            <div className="grid grid-cols-3 gap-2">
              {(["both", "same", "opposite"] as const).map((strand) => {
                const selected = (colocationParams?.strand ?? "both") === strand;
                return (
                  <button
                    key={strand}
                    type="button"
                    onClick={() =>
                      onColocationParamsChange({
                        upstream: colocationParams?.upstream ?? 0,
                        downstream: colocationParams?.downstream ?? 0,
                        strand,
                      })
                    }
                    className={`rounded-md border px-2 py-2 text-sm font-semibold transition-colors duration-150 ${
                      selected
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-border bg-card text-foreground hover:border-input"
                    }`}
                  >
                    {strand.toUpperCase()}
                  </button>
                );
              })}
            </div>
          </label>
        </div>
      )}
    </div>
  );
}

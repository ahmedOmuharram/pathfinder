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
      <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-slate-500">
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
              className={`flex items-center justify-between rounded-md border px-3 py-2 text-left ${
                selected
                  ? "border-slate-900 bg-white"
                  : "border-slate-200 bg-white hover:border-slate-300"
              }`}
            >
              <div className="flex flex-col">
                <div className="flex items-center gap-2">
                  <OpBadge operator={op} size="sm" />
                  <span className="text-[12px] font-semibold text-slate-800">
                    {CombineOperatorLabels[op]}
                  </span>
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {showColocate && (
        <div className="mt-3 space-y-2 rounded-md border border-slate-200 bg-white p-3">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            Colocation parameters
          </div>
          <div className="grid grid-cols-2 gap-2">
            <label className="text-[12px] text-slate-700">
              <div className="mb-1 text-[11px] text-slate-500">Upstream (bp)</div>
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
                className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-[13px] text-slate-800"
              />
            </label>
            <label className="text-[12px] text-slate-700">
              <div className="mb-1 text-[11px] text-slate-500">Downstream (bp)</div>
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
                className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-[13px] text-slate-800"
              />
            </label>
          </div>
          <label className="text-[12px] text-slate-700">
            <div className="mb-1 text-[11px] text-slate-500">Strand</div>
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
                    className={`rounded-md border px-2 py-2 text-[12px] font-semibold ${
                      selected
                        ? "border-slate-900 bg-slate-900 text-white"
                        : "border-slate-200 bg-white text-slate-700 hover:border-slate-300"
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

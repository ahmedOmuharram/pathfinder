"use client";

import { CombineOperator } from "@pathfinder/shared";

type StepCombineOperatorSelectProps = {
  operatorValue: string;
  onOperatorChange: (nextValue: string) => void;
};

const COMBINE_OPERATORS = Object.values(CombineOperator);

export function StepCombineOperatorSelect({
  operatorValue,
  onOperatorChange,
}: StepCombineOperatorSelectProps) {
  return (
    <div>
      <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-slate-500">
        Operator
      </label>
      <select
        value={operatorValue}
        onChange={(event) => onOperatorChange(event.target.value)}
        className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-[13px] text-slate-800"
      >
        <option value="">Select...</option>
        {COMBINE_OPERATORS.map((op) => (
          <option key={op} value={op}>
            {op}
          </option>
        ))}
      </select>
    </div>
  );
}

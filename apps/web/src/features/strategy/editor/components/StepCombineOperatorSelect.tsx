"use client";

import type { ColocationParams } from "@pathfinder/shared";
import { CombineOperator, CombineOperatorLabels } from "@pathfinder/shared";
import { OpBadge } from "@/features/strategy/graph/components/OpBadge";
import { Label } from "@/lib/components/ui/Label";
import { ColocationEditor, resolveParams } from "@/features/strategy/editor/components/ColocationEditor";
import type { ColocationFormValues } from "../schema/colocationSchema";

type StepCombineOperatorSelectProps = {
  operatorValue: string;
  onOperatorChange: (nextValue: string) => void;
  colocationParams?: ColocationParams | null | undefined;
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
  const resolved = resolveParams(colocationParams);

  function handleColocationChange(values: ColocationFormValues) {
    onColocationParamsChange(values);
  }

  return (
    <div>
      <Label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Operator
      </Label>
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
        <ColocationEditor
          initialValues={resolved}
          onChange={handleColocationChange}
        />
      )}
    </div>
  );
}

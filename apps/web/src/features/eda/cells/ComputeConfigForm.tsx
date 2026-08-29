"use client";

import type { ReactNode } from "react";
import type { EdaVariableResponse } from "@pathfinder/shared/generated/types/EdaVariableResponse";

import type {
  ComputeConfigDraft,
  DifferentialExpressionMethod,
} from "../computeConfig";

const SELECT_CLASS =
  "h-8 w-full rounded-md border border-input bg-background px-2 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-ring";

const METHODS: { value: DifferentialExpressionMethod; label: string }[] = [
  { value: "DESeq", label: "DESeq2" },
  { value: "limma", label: "limma" },
];

export interface ComputeConfigFormProps {
  draft: ComputeConfigDraft;
  values: readonly EdaVariableResponse[];
  comparators: readonly EdaVariableResponse[];
  onChange: (next: ComputeConfigDraft) => void;
}

export function ComputeConfigForm({
  draft,
  values,
  comparators,
  onChange,
}: ComputeConfigFormProps) {
  const comparator =
    comparators.find(
      (variable) => variable.variableId === draft.comparatorVariableId,
    ) ?? null;
  const vocabulary = comparator?.vocabulary ?? [];

  return (
    <div className="grid grid-cols-2 gap-3">
      <Field id="eda-compute-analysis" label="Analysis">
        <select
          id="eda-compute-analysis"
          className={SELECT_CLASS}
          defaultValue="differentialexpression"
        >
          <option value="differentialexpression">Differential expression</option>
        </select>
      </Field>

      <Field id="eda-compute-method" label="Method">
        <select
          id="eda-compute-method"
          className={SELECT_CLASS}
          value={draft.method}
          onChange={(event) =>
            onChange({
              ...draft,
              method: event.target.value === "limma" ? "limma" : "DESeq",
            })
          }
        >
          {METHODS.map((method) => (
            <option key={method.value} value={method.value}>
              {method.label}
            </option>
          ))}
        </select>
      </Field>

      <Field id="eda-compute-value-variable" label="Value variable">
        <select
          id="eda-compute-value-variable"
          className={SELECT_CLASS}
          value={draft.valueVariableId}
          onChange={(event) =>
            onChange({ ...draft, valueVariableId: event.target.value })
          }
        >
          {values.map((variable) => (
            <option key={variable.variableId} value={variable.variableId}>
              {variable.displayName}
            </option>
          ))}
        </select>
      </Field>

      <Field id="eda-compute-comparator" label="Comparator variable">
        <select
          id="eda-compute-comparator"
          className={SELECT_CLASS}
          value={draft.comparatorVariableId}
          onChange={(event) => {
            const chosen =
              comparators.find(
                (variable) => variable.variableId === event.target.value,
              ) ?? null;
            onChange({
              ...draft,
              comparatorEntityId: chosen?.entityId ?? "",
              comparatorVariableId: chosen?.variableId ?? "",
              groupA: [],
              groupB: [],
            });
          }}
        >
          <option value="">Choose a variable...</option>
          {comparators.map((variable) => (
            <option key={variable.variableId} value={variable.variableId}>
              {variable.displayName}
            </option>
          ))}
        </select>
      </Field>

      <GroupField
        id="eda-compute-group-a"
        label="Group A"
        value={draft.groupA[0] ?? ""}
        vocabulary={vocabulary}
        onChange={(label) =>
          onChange({ ...draft, groupA: label === "" ? [] : [label] })
        }
      />
      <GroupField
        id="eda-compute-group-b"
        label="Group B"
        value={draft.groupB[0] ?? ""}
        vocabulary={vocabulary}
        onChange={(label) =>
          onChange({ ...draft, groupB: label === "" ? [] : [label] })
        }
      />
    </div>
  );
}

function Field({
  id,
  label,
  children,
}: {
  id: string;
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="block text-[11px] text-muted-foreground">
        {label}
      </label>
      {children}
    </div>
  );
}

function GroupField({
  id,
  label,
  value,
  vocabulary,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  vocabulary: readonly string[];
  onChange: (label: string) => void;
}) {
  return (
    <Field id={id} label={label}>
      <select
        id={id}
        className={SELECT_CLASS}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">Choose a value...</option>
        {vocabulary.map((entry) => (
          <option key={entry} value={entry}>
            {entry}
          </option>
        ))}
      </select>
    </Field>
  );
}

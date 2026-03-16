"use client";

import type { Dispatch, SetStateAction } from "react";
import { extractVocabTree, type VocabOption } from "@/lib/utils/vocab";
import { extractSpecVocabulary } from "./stepEditorUtils";
import { isMultiParam, type ParamSpec } from "@/features/strategy/parameters/spec";
import { SingleValueField } from "./SingleValueField";
import { MultiValueField } from "./MultiValueField";
import type { StepParameters } from "@/lib/strategyGraph/types";
import { Label } from "@/lib/components/ui/Label";

type StepParamFieldsProps = {
  paramSpecs: ParamSpec[];
  showRaw: boolean;
  parameters: StepParameters;
  vocabOptions: Record<string, VocabOption[]>;
  dependentOptions: Record<string, VocabOption[]>;
  dependentLoading: Record<string, boolean>;
  dependentErrors: Record<string, string | null>;
  validationErrorKeys: Set<string>;
  setParameters: Dispatch<SetStateAction<StepParameters>>;
};

export function StepParamFields({
  paramSpecs,
  showRaw,
  parameters,
  vocabOptions,
  dependentOptions,
  dependentLoading,
  dependentErrors,
  validationErrorKeys,
  setParameters,
}: StepParamFieldsProps) {
  if (showRaw) return null;

  if (paramSpecs.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        No parameter options available. Use advanced editing to view or edit raw JSON.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {paramSpecs.map((spec) => {
        if (!spec.name) return null;
        const paramName = spec.name;
        const label = spec.displayName || paramName;
        const options = vocabOptions[paramName] || dependentOptions[paramName] || [];
        const value = parameters[paramName];
        const multi = isMultiParam(spec);
        const vocabulary = extractSpecVocabulary(spec);
        const vocabTree = multi ? extractVocabTree(vocabulary) : null;
        const valueSet = new Set(options.map((opt) => opt.value));
        const labelToValue = new Map(
          options.map((opt) => [opt.rawLabel ?? opt.label, opt.value]),
        );
        const normalizeValue = (raw: unknown): string[] => {
          if (raw === null || raw === undefined) return [];
          const list = Array.isArray(raw) ? raw : [raw];
          return list
            .map((entry) => {
              const str = String(entry);
              if (valueSet.has(str)) return str;
              return labelToValue.get(str) || str;
            })
            .filter((entry) => entry !== "");
        };
        const hasFieldError = validationErrorKeys.has(paramName);
        const fieldWrapperClass = hasFieldError
          ? "rounded-md border border-destructive/20 bg-destructive/5 p-2"
          : "";
        const fieldLabelClass = hasFieldError
          ? "mb-1 block text-xs font-semibold uppercase tracking-wide text-destructive"
          : "mb-1 block text-xs font-semibold uppercase tracking-wide text-muted-foreground";
        const fieldBorderClass = hasFieldError
          ? "border-destructive/30 bg-destructive/5"
          : "border-border bg-card";

        return (
          <div key={paramName} className={fieldWrapperClass}>
            <Label className={fieldLabelClass}>
              {label}
              {spec.allowEmptyValue === false && (
                <span className="ml-1 text-destructive">*</span>
              )}
            </Label>
            {multi ? (
              <MultiValueField
                paramName={paramName}
                spec={spec}
                value={value}
                options={options}
                vocabTree={vocabTree}
                fieldBorderClass={fieldBorderClass}
                setParameters={setParameters}
              />
            ) : (
              <SingleValueField
                paramName={paramName}
                spec={spec}
                value={value}
                options={options}
                vocabTree={vocabTree}
                normalizedValue={normalizeValue(value)}
                fieldBorderClass={fieldBorderClass}
                setParameters={setParameters}
              />
            )}
            <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
              {dependentLoading[paramName] && <span>Loading options...</span>}
              {dependentErrors[paramName] && (
                <span className="text-destructive">{dependentErrors[paramName]}</span>
              )}
              {options.length === 0 && (
                <span className="text-muted-foreground">
                  Use advanced editing if needed.
                </span>
              )}
            </div>
            {spec.help && (
              <p className="mt-1 text-xs text-muted-foreground">{spec.help}</p>
            )}
          </div>
        );
      })}
    </div>
  );
}

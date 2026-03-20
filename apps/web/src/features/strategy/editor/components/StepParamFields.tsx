"use client";

import type { Dispatch, SetStateAction } from "react";
import { useMemo } from "react";
import { extractVocabTree, type VocabOption } from "@/lib/utils/vocab";
import { extractSpecVocabulary } from "./stepEditorUtils";
import { isMultiParam, type ParamSpec } from "@/features/strategy/parameters/spec";
import type { StepParameters } from "@/lib/strategyGraph/types";
import { Label } from "@/lib/components/ui/Label";
import {
  resolveDisplayType,
  isHiddenParam,
  isAdvancedParam,
  DISPLAY_TYPES,
} from "../widgets/registry";
import { StringParam } from "../widgets/StringParam";
import { SelectParam } from "../widgets/SelectParam";
import { CheckboxParam } from "../widgets/CheckboxParam";
import { TreeBoxParam } from "../widgets/TreeBoxParam";
import { TypeAheadParam } from "../widgets/TypeAheadParam";
import {
  PhyleticProfileParam,
  claimsPhyleticParams,
} from "../widgets/PhyleticProfileParam";
import { AdvancedParamsGroup } from "../widgets/AdvancedParamsGroup";
import type { ParamWidgetProps } from "../widgets/types";

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

// ---------------------------------------------------------------------------
// Widget dispatch — maps displayType to component
// ---------------------------------------------------------------------------

function renderWidget(displayType: string, props: ParamWidgetProps): React.ReactNode {
  switch (displayType) {
    case DISPLAY_TYPES.TREE_BOX:
      return <TreeBoxParam {...props} />;
    case DISPLAY_TYPES.TYPE_AHEAD:
      return <TypeAheadParam {...props} />;
    case DISPLAY_TYPES.SELECT:
      return <SelectParam {...props} />;
    case DISPLAY_TYPES.CHECK_BOX:
      return <CheckboxParam {...props} />;
    default:
      return <StringParam {...props} />;
  }
}

// ---------------------------------------------------------------------------
// Value coercion helpers
// ---------------------------------------------------------------------------

function toSingleValue(raw: unknown): string | undefined {
  if (raw === null || raw === undefined) return undefined;
  if (Array.isArray(raw)) return raw.length > 0 ? String(raw[0]) : undefined;
  return String(raw);
}

function toMultiValue(raw: unknown, options: VocabOption[]): string[] {
  if (raw === null || raw === undefined) return [];

  // WDK wire format stores multi-pick values as JSON-encoded strings.
  // Decode them before matching against options.
  let decoded: unknown = raw;
  if (typeof raw === "string") {
    const trimmed = raw.trim();
    if (trimmed.startsWith("[") && trimmed.endsWith("]")) {
      try {
        const parsed: unknown = JSON.parse(trimmed);
        if (Array.isArray(parsed)) decoded = parsed;
      } catch {
        /* not JSON, use as-is */
      }
    }
  }

  const valueSet = new Set(options.map((o) => o.value));
  const labelToValue = new Map(options.map((o) => [o.rawLabel ?? o.label, o.value]));
  const list = Array.isArray(decoded) ? decoded : [decoded];
  return list
    .map((entry) => {
      const str = String(entry);
      if (valueSet.has(str)) return str;
      return labelToValue.get(str) ?? str;
    })
    .filter((s) => s !== "");
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

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
  // 1. Detect composite widgets
  const claimedParamNames = useMemo(
    () => new Set(claimsPhyleticParams(paramSpecs)),
    [paramSpecs],
  );

  // 2. Separate params into groups
  const { compositeSpecs, normalSpecs, advancedSpecs } = useMemo(() => {
    const composite: ParamSpec[] = [];
    const normal: ParamSpec[] = [];
    const advanced: ParamSpec[] = [];
    for (const spec of paramSpecs) {
      if (spec.name == null || spec.name === "") continue;
      if (claimedParamNames.has(spec.name)) {
        composite.push(spec);
        continue;
      }
      if (isHiddenParam(spec)) continue; // hidden, handled by hiddenDefaults
      if (isAdvancedParam(spec)) {
        advanced.push(spec);
      } else {
        normal.push(spec);
      }
    }
    return { compositeSpecs: composite, normalSpecs: normal, advancedSpecs: advanced };
  }, [paramSpecs, claimedParamNames]);

  if (showRaw) return null;

  const visibleCount = normalSpecs.length + advancedSpecs.length;
  const hasComposite = compositeSpecs.length > 0;

  if (visibleCount === 0 && !hasComposite) {
    return (
      <p className="text-xs text-muted-foreground">
        No parameter options available. Use advanced editing to view or edit raw JSON.
      </p>
    );
  }

  // Shared handler for composite widget
  const handleCompositeChange = (updates: StepParameters) => {
    setParameters((prev) => ({ ...prev, ...updates }));
  };

  return (
    <div className="space-y-3">
      {/* Composite widgets */}
      {hasComposite && (
        <PhyleticProfileParam
          specs={compositeSpecs}
          allSpecs={paramSpecs}
          parameters={parameters}
          onChange={handleCompositeChange}
        />
      )}

      {/* Normal params */}
      {normalSpecs.map((spec) => (
        <ParamField
          key={spec.name}
          spec={spec}
          parameters={parameters}
          vocabOptions={vocabOptions}
          dependentOptions={dependentOptions}
          dependentLoading={dependentLoading}
          dependentErrors={dependentErrors}
          validationErrorKeys={validationErrorKeys}
          setParameters={setParameters}
        />
      ))}

      {/* Advanced params (collapsible) */}
      {advancedSpecs.length > 0 && (
        <AdvancedParamsGroup
          count={advancedSpecs.length}
          hasErrors={advancedSpecs.some(
            (s) => s.name != null && s.name !== "" && validationErrorKeys.has(s.name),
          )}
        >
          {advancedSpecs.map((spec) => (
            <ParamField
              key={spec.name}
              spec={spec}
              parameters={parameters}
              vocabOptions={vocabOptions}
              dependentOptions={dependentOptions}
              dependentLoading={dependentLoading}
              dependentErrors={dependentErrors}
              validationErrorKeys={validationErrorKeys}
              setParameters={setParameters}
            />
          ))}
        </AdvancedParamsGroup>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Individual param field — wraps a widget with label, error, help
// ---------------------------------------------------------------------------

function ParamField({
  spec,
  parameters,
  vocabOptions,
  dependentOptions,
  dependentLoading,
  dependentErrors,
  validationErrorKeys,
  setParameters,
}: {
  spec: ParamSpec;
  parameters: StepParameters;
  vocabOptions: Record<string, VocabOption[]>;
  dependentOptions: Record<string, VocabOption[]>;
  dependentLoading: Record<string, boolean>;
  dependentErrors: Record<string, string | null>;
  validationErrorKeys: Set<string>;
  setParameters: Dispatch<SetStateAction<StepParameters>>;
}) {
  const paramName = spec.name ?? "";
  const label = spec.displayName ?? paramName;
  const options = vocabOptions[paramName] ?? dependentOptions[paramName] ?? [];
  const rawValue = parameters[paramName];
  const multi = isMultiParam(spec);
  const vocabulary = extractSpecVocabulary(spec);
  const vocabTree = extractVocabTree(vocabulary);
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

  const displayType = resolveDisplayType(spec);

  const onChangeSingle = (value: string) => {
    setParameters((prev) => ({ ...prev, [paramName]: value }));
  };
  const onChangeMulti = (value: string[]) => {
    setParameters((prev) => ({ ...prev, [paramName]: value }));
  };

  return (
    <div className={fieldWrapperClass}>
      <Label className={fieldLabelClass}>
        {label}
        {spec.allowEmptyValue != null && spec.allowEmptyValue === false && (
          <span className="ml-1 text-destructive">*</span>
        )}
      </Label>
      {renderWidget(displayType, {
        spec,
        value: toSingleValue(rawValue),
        multi,
        multiValue: toMultiValue(rawValue, options),
        options,
        vocabTree,
        onChangeSingle,
        onChangeMulti,
        fieldBorderClass,
      })}
      <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
        {dependentLoading[paramName] === true && <span>Loading options...</span>}
        {dependentErrors[paramName] != null && dependentErrors[paramName] !== "" && (
          <span className="text-destructive">{dependentErrors[paramName]}</span>
        )}
      </div>
      {spec.help != null && spec.help !== "" && (
        <p className="mt-1 text-xs text-muted-foreground">{spec.help}</p>
      )}
    </div>
  );
}

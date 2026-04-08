"use client";

import { FormProvider, useFormContext, type UseFormReturn } from "react-hook-form";
import { extractVocabTree, type VocabOption } from "@/lib/utils/vocab";
import { extractSpecVocabulary } from "./stepEditorUtils";
import type { ParamSpec } from "@/features/strategy/parameters/spec";
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
import { useDependentParams } from "../hooks/useDependentParams";

type StepParamFieldsProps = {
  /** RHF form instance owned by the parent. */
  form: UseFormReturn;
  paramSpecs: ParamSpec[];
  vocabOptions: Record<string, VocabOption[]>;
  /** Site identifier (e.g. "plasmodb") for dependent param refresh. */
  siteId: string;
  /** Normalized record type (e.g. "transcript") for dependent param refresh. */
  recordType: string;
  /** WDK search name (e.g. "GenesByTaxon") for dependent param refresh. */
  searchName: string;
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
// Main component
// ---------------------------------------------------------------------------

export function StepParamFields({
  form,
  paramSpecs,
  vocabOptions,
  siteId,
  recordType,
  searchName,
}: StepParamFieldsProps) {
  // Dependent param refresh — driven by form watch internally.
  const { dependentOptions, dependentLoading, dependentErrors } = useDependentParams({
    control: form.control,
    specs: paramSpecs,
    siteId,
    recordType,
    searchName,
  });

  // 1. Detect composite widgets
  const claimedParamNames = new Set(claimsPhyleticParams(paramSpecs));

  // 2. Separate params into groups
  const { compositeSpecs, normalSpecs, advancedSpecs } = (() => {
    const composite: ParamSpec[] = [];
    const normal: ParamSpec[] = [];
    const advanced: ParamSpec[] = [];
    for (const spec of paramSpecs) {
      if (spec.name === "") continue;
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
  })();

  const visibleCount = normalSpecs.length + advancedSpecs.length;
  const hasComposite = compositeSpecs.length > 0;

  if (visibleCount === 0 && !hasComposite) {
    return (
      <p className="text-xs text-muted-foreground">
        No parameter options available. Use advanced editing to view or edit raw JSON.
      </p>
    );
  }

  return (
    <FormProvider {...form}>
      <div className="space-y-3">
        {/* Composite widgets */}
        {hasComposite && (
          <PhyleticProfileParam
            specs={compositeSpecs}
            allSpecs={paramSpecs}
          />
        )}

        {/* Normal params */}
        {normalSpecs.map((spec) => (
          <ParamField
            key={spec.name}
            spec={spec}
            vocabOptions={vocabOptions}
            dependentOptions={dependentOptions}
            dependentLoading={dependentLoading}
            dependentErrors={dependentErrors}
          />
        ))}

        {/* Advanced params (collapsible) */}
        {advancedSpecs.length > 0 && (
          <AdvancedParamsGroup
            count={advancedSpecs.length}
            hasErrors={advancedSpecs.some(
              (s) => s.name !== "" && form.formState.errors[s.name] != null,
            )}
          >
            {advancedSpecs.map((spec) => (
              <ParamField
                key={spec.name}
                spec={spec}
                vocabOptions={vocabOptions}
                dependentOptions={dependentOptions}
                dependentLoading={dependentLoading}
                dependentErrors={dependentErrors}
              />
            ))}
          </AdvancedParamsGroup>
        )}
      </div>
    </FormProvider>
  );
}

// ---------------------------------------------------------------------------
// Individual param field — wraps a widget with label, help, dependent status
// ---------------------------------------------------------------------------

function ParamField({
  spec,
  vocabOptions,
  dependentOptions,
  dependentLoading,
  dependentErrors,
}: {
  spec: ParamSpec;
  vocabOptions: Record<string, VocabOption[]>;
  dependentOptions: Record<string, VocabOption[]>;
  dependentLoading: Record<string, boolean>;
  dependentErrors: Record<string, string | null>;
}) {
  const { formState: { errors } } = useFormContext();

  const paramName = spec.name;
  const label = spec.displayName ?? paramName;
  const options = vocabOptions[paramName] ?? dependentOptions[paramName] ?? [];
  const vocabulary = extractSpecVocabulary(spec);
  const vocabTree = extractVocabTree(vocabulary);
  const hasFieldError = errors[paramName] != null;

  const fieldWrapperClass = hasFieldError
    ? "rounded-md border border-destructive/20 bg-destructive/5 p-2"
    : "";
  const fieldLabelClass = hasFieldError
    ? "mb-1 block text-xs font-semibold uppercase tracking-wide text-destructive"
    : "mb-1 block text-xs font-semibold uppercase tracking-wide text-muted-foreground";

  const displayType = resolveDisplayType(spec);

  return (
    <div className={fieldWrapperClass}>
      <Label className={fieldLabelClass}>
        {label}
        {spec.allowEmptyValue === false && (
          <span className="ml-1 text-destructive">*</span>
        )}
      </Label>
      {renderWidget(displayType, {
        spec,
        name: paramName,
        options,
        vocabTree,
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

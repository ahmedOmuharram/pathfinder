"use client";

import { extractVocabTree, type VocabOption } from "@/lib/utils/vocab";
import { extractSpecVocabulary } from "./stepEditorUtils";
import type { ParamSpec } from "@/features/strategy/parameters/spec";
import type { ParamForm } from "../hooks/useParamForm";
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
import { buildFieldSchema } from "../schema/paramSchema";

type StepParamFieldsProps = {
  form: ParamForm;
  paramSpecs: ParamSpec[];
  vocabOptions: Record<string, VocabOption[]>;
  dependentOptions: Record<string, VocabOption[]>;
  dependentLoading: Record<string, boolean>;
  dependentErrors: Record<string, string | null>;
};

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

export function StepParamFields({
  form,
  paramSpecs,
  vocabOptions,
  dependentOptions,
  dependentLoading,
  dependentErrors,
}: StepParamFieldsProps) {
  const claimedParamNames = new Set(claimsPhyleticParams(paramSpecs));

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
      if (isHiddenParam(spec)) continue;
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

  const advancedHasErrors = advancedSpecs.some((s) => {
    const meta = form.getFieldMeta(s.name);
    return meta != null && meta.errors.length > 0;
  });

  return (
    <div className="space-y-3">
      {hasComposite && (
        <PhyleticProfileParam
          specs={compositeSpecs}
          allSpecs={paramSpecs}
          form={form}
        />
      )}

      {normalSpecs.map((spec) => (
        <ParamField
          key={spec.name}
          spec={spec}
          form={form}
          vocabOptions={vocabOptions}
          dependentOptions={dependentOptions}
          dependentLoading={dependentLoading}
          dependentErrors={dependentErrors}
        />
      ))}

      {advancedSpecs.length > 0 && (
        <AdvancedParamsGroup count={advancedSpecs.length} hasErrors={advancedHasErrors}>
          {advancedSpecs.map((spec) => (
            <ParamField
              key={spec.name}
              spec={spec}
              form={form}
              vocabOptions={vocabOptions}
              dependentOptions={dependentOptions}
              dependentLoading={dependentLoading}
              dependentErrors={dependentErrors}
            />
          ))}
        </AdvancedParamsGroup>
      )}
    </div>
  );
}

function ParamField({
  spec,
  form,
  vocabOptions,
  dependentOptions,
  dependentLoading,
  dependentErrors,
}: {
  spec: ParamSpec;
  form: ParamForm;
  vocabOptions: Record<string, VocabOption[]>;
  dependentOptions: Record<string, VocabOption[]>;
  dependentLoading: Record<string, boolean>;
  dependentErrors: Record<string, string | null>;
}) {
  const paramName = spec.name;
  const label = spec.displayName ?? paramName;
  const options = vocabOptions[paramName] ?? dependentOptions[paramName] ?? [];
  const vocabulary = extractSpecVocabulary(spec);
  const vocabTree = extractVocabTree(vocabulary);
  const displayType = resolveDisplayType(spec);
  const fieldSchema = buildFieldSchema(spec);

  return (
    <form.Field
      name={paramName}
      validators={{
        onBlur: ({ value }) => {
          const result = fieldSchema.safeParse(value);
          if (result.success) return undefined;
          return result.error.issues[0]?.message ?? "Invalid value";
        },
      }}
    >
      {(field) => {
        const fieldApi = field as unknown as ParamWidgetProps["field"];
        const hasFieldError = field.state.meta.errors.length > 0;

        const fieldWrapperClass = hasFieldError
          ? "rounded-md border border-destructive/20 bg-destructive/5 p-2"
          : "";
        const fieldLabelClass = hasFieldError
          ? "mb-1 block text-xs font-semibold uppercase tracking-wide text-destructive"
          : "mb-1 block text-xs font-semibold uppercase tracking-wide text-muted-foreground";

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
              field: fieldApi,
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
      }}
    </form.Field>
  );
}

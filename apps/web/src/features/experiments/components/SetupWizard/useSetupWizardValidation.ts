import { useMemo } from "react";
import type { ParamSpec } from "@pathfinder/shared";
import { isParamRequired, isParamEmpty } from "../paramUtils";
import { computeStepValidation } from "./stepValidation";

interface ValidationInput {
  step: number;
  selectedSearch: string;
  selectedRecordType: string;
  paramSpecs: ParamSpec[];
  paramSpecsLoading: boolean;
  parameters: Record<string, string>;
  positiveGenes: { geneId: string }[];
  negativeGenes: { geneId: string }[];
}

export function useSetupWizardValidation(input: ValidationInput) {
  const {
    step,
    selectedSearch,
    selectedRecordType,
    paramSpecs,
    paramSpecsLoading,
    parameters,
    positiveGenes,
    negativeGenes,
  } = input;

  const positiveControls = useMemo(
    () => positiveGenes.map((g) => g.geneId),
    [positiveGenes],
  );

  const negativeControls = useMemo(
    () => negativeGenes.map((g) => g.geneId),
    [negativeGenes],
  );

  const isTransformSearch = useMemo(
    () => paramSpecs.some((s) => s.type === "input-step"),
    [paramSpecs],
  );

  const visibleParamSpecs = useMemo(
    () => paramSpecs.filter((s) => s.type !== "input-step"),
    [paramSpecs],
  );

  const emptyRequiredParams = useMemo(
    () =>
      visibleParamSpecs.filter(
        (spec) =>
          isParamRequired(spec) && isParamEmpty(spec, parameters[spec.name] ?? ""),
      ),
    [visibleParamSpecs, parameters],
  );

  const stepValidation = useMemo(
    () =>
      computeStepValidation({
        step,
        selectedSearch,
        paramSpecsLoading,
        emptyRequiredParams,
        positiveControls,
        negativeControls,
      }),
    [
      step,
      selectedSearch,
      paramSpecsLoading,
      emptyRequiredParams,
      positiveControls,
      negativeControls,
    ],
  );

  const aiContext = useMemo(
    () => ({
      recordType: selectedRecordType,
      searchName: selectedSearch,
      parameters,
      positiveControls,
      negativeControls,
    }),
    [
      selectedRecordType,
      selectedSearch,
      parameters,
      positiveControls,
      negativeControls,
    ],
  );

  return {
    positiveControls,
    negativeControls,
    isTransformSearch,
    visibleParamSpecs,
    stepValidation,
    aiContext,
  };
}

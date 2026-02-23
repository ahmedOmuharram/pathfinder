import type { ParamSpec } from "@pathfinder/shared";

export interface StepValidationResult {
  valid: boolean;
  message: string | null;
}

export function computeStepValidation(args: {
  step: number;
  selectedSearch: string;
  paramSpecsLoading: boolean;
  emptyRequiredParams: ParamSpec[];
  positiveControls: string[];
  negativeControls: string[];
}): StepValidationResult {
  const {
    step,
    selectedSearch,
    paramSpecsLoading,
    emptyRequiredParams,
    positiveControls,
    negativeControls,
  } = args;

  switch (step) {
    case 0:
      if (!selectedSearch)
        return { valid: false, message: "Select a search to continue" };
      return { valid: true, message: null };
    case 1: {
      if (paramSpecsLoading) return { valid: false, message: "Loading parameters..." };
      if (emptyRequiredParams.length > 0) {
        const names = emptyRequiredParams
          .slice(0, 3)
          .map((s) => s.displayName || s.name);
        const more =
          emptyRequiredParams.length > 3
            ? ` and ${emptyRequiredParams.length - 3} more`
            : "";
        return {
          valid: false,
          message: `Required parameters missing: ${names.join(", ")}${more}`,
        };
      }
      return { valid: true, message: null };
    }
    case 2:
      if (positiveControls.length === 0 && negativeControls.length === 0)
        return {
          valid: false,
          message: "Add at least one positive or negative control gene",
        };
      return { valid: true, message: null };
    case 3:
      return { valid: true, message: null };
    default:
      return { valid: false, message: null };
  }
}

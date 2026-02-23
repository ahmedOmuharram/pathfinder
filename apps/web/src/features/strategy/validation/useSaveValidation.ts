import { useEffect, useMemo } from "react";
import type { StrategyStep, StrategyWithMeta } from "@/features/strategy/types";

export function useSaveValidation(args: {
  steps: StrategyStep[];
  buildStepSignature: (step: StrategyStep) => string;
  debounceMs?: number;
  validate: () => Promise<boolean>;
  strategy: StrategyWithMeta | null;
}) {
  const { steps, buildStepSignature, debounceMs = 500, validate } = args;

  const validationInputKey = useMemo(() => {
    if (steps.length === 0) return "";
    return steps
      .map((step) => `${step.id}:${buildStepSignature(step)}`)
      .sort()
      .join("|");
  }, [steps, buildStepSignature]);

  useEffect(() => {
    if (steps.length === 0) return;
    const timeout = window.setTimeout(() => {
      void validate();
    }, debounceMs);
    return () => window.clearTimeout(timeout);
  }, [steps, validationInputKey, validate, debounceMs]);
}

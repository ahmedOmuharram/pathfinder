"use client";

import { useMemo, useState } from "react";
import type { ParamSpec } from "@pathfinder/shared";

interface UseStepValidationArgs {
  stepValidationError: string | null | undefined;
  paramSpecs: ParamSpec[];
}

export function useStepValidation({
  stepValidationError,
  paramSpecs,
}: UseStepValidationArgs) {
  const [error, setError] = useState<string | null>(null);

  const validationErrorKeys = useMemo(() => {
    if (stepValidationError == null || stepValidationError === "")
      return new Set<string>();
    const keys = new Set<string>();
    const paramNames = new Set(
      paramSpecs.map((spec) => spec.name).filter((n) => n !== ""),
    );
    stepValidationError
      .replace(/^Cannot be saved:\s*/i, "")
      .split(";")
      .map((part) => part.trim())
      .forEach((part) => {
        if (!part) return;
        const splitIndex = part.indexOf(":");
        if (splitIndex === -1) return;
        const key = part.slice(0, splitIndex).trim();
        if (paramNames.has(key)) {
          keys.add(key);
        }
      });
    return keys;
  }, [stepValidationError, paramSpecs]);

  return {
    error,
    setError,
    validationErrorKeys,
  };
}

import type { ReadonlyStore } from "@tanstack/react-store";

export interface OptimizeFormValues {
  stepId: number | null;
  paramKeys: string[];
  criterion: string;
  budget: number;
  modelId: string;
}

export interface StepLite {
  id: string;
  searchName?: string | null | undefined;
  displayName?: string | null | undefined;
}

export interface ModelOption {
  id: string;
  name?: string | null | undefined;
}

/**
 * Minimal slice of the TanStack Form return value used by the field
 * components. Avoids dragging the 11-generic `ReactFormExtendedApi` type
 * across module boundaries. The `OptimizeLauncherForm` adapts its real form
 * into this shape via `toLauncherForm` below.
 */
export interface LauncherForm {
  store: ReadonlyStore<{ values: OptimizeFormValues }>;
  setStepId: (value: number | null) => void;
  setParamKeys: (value: string[]) => void;
  setCriterion: (value: string) => void;
  setBudget: (value: number) => void;
  setModelId: (value: string) => void;
}

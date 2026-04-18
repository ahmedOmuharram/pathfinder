import { useShallow } from "zustand/react/shallow";
import type { SearchValidationErrors, Step } from "@pathfinder/shared";
import { useStrategyStore } from "./store";
import type {
  StepLifecycleStateName,
  StepMachineSnapshot,
} from "./stepMachine";

export interface StepSnapshot {
  step: Step | null;
  /** Current XState v5 leaf state for the step. */
  lifecycleState: StepLifecycleStateName;
  /** Cached estimatedSize — lifecycle context wins over wire field. */
  estimatedSize: number | null;
  /** Validation errors from the lifecycle machine, falling back to wire. */
  validationErrors: SearchValidationErrors | null;
  /** Last transient error (network/server) from the lifecycle machine. */
  lastError: string | null;
  /** True when the lifecycle is in validating or running. */
  isBusy: boolean;
  /** True when the step has a hard validation failure. */
  isInvalid: boolean;
  /** True when the step suffered a transient run/validation failure. */
  isFailed: boolean;
}

function pickLifecycleValue(
  snapshot: StepMachineSnapshot | undefined,
): StepLifecycleStateName {
  if (!snapshot) return "idle";
  const value = snapshot.value;
  if (typeof value === "string") return value as StepLifecycleStateName;
  return "idle";
}

function resolveEstimatedSize(
  snapshot: StepMachineSnapshot | undefined,
  wire: Step | null,
): number | null {
  if (snapshot && snapshot.context.estimatedSize !== null) {
    return snapshot.context.estimatedSize;
  }
  const wireSize = wire?.estimatedSize;
  return typeof wireSize === "number" ? wireSize : null;
}

const wireErrorsCache = new WeakMap<object, SearchValidationErrors>();

function resolveValidationErrors(
  snapshot: StepMachineSnapshot | undefined,
  wire: Step | null,
): SearchValidationErrors | null {
  if (snapshot?.context.validationErrors) {
    return snapshot.context.validationErrors;
  }
  const wireErrors = wire?.validation?.errors;
  if (!wireErrors) return null;
  const cached = wireErrorsCache.get(wireErrors);
  if (cached) return cached;
  const normalized: SearchValidationErrors = {
    general: wireErrors.general ?? [],
    byKey: wireErrors.byKey ?? {},
  };
  wireErrorsCache.set(wireErrors, normalized);
  return normalized;
}

export function useStepSnapshot(stepId: string): StepSnapshot {
  return useStrategyStore(
    useShallow((state) => {
      const step = state.stepsById[stepId] ?? null;
      const lifecycle = state.stepLifecycleById[stepId];
      const lifecycleState = pickLifecycleValue(lifecycle);
      return {
        step,
        lifecycleState,
        estimatedSize: resolveEstimatedSize(lifecycle, step),
        validationErrors: resolveValidationErrors(lifecycle, step),
        lastError: lifecycle?.context.lastError ?? null,
        isBusy:
          lifecycleState === "validating" || lifecycleState === "running",
        isInvalid: lifecycleState === "invalid",
        isFailed: lifecycleState === "failed",
      };
    }),
  );
}

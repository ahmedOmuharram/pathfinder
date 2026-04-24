/**
 * @vitest-environment jsdom
 */
import { beforeEach, describe, expect, it } from "vitest";
import { renderHook } from "@testing-library/react";
import type { Step } from "@pathfinder/shared";
import { useStrategyStore } from "./store";
import { useStepSnapshot } from "./useStepSnapshot";

function makeStep(overrides: Partial<Step> = {}): Step {
  return {
    id: "s1",
    displayName: "Step 1",
    searchName: "GenesByTaxon",
    recordType: "gene",
    parameters: {},
    estimatedSize: null,
    isBuilt: false,
    isFiltered: false,
    validation: null,
    ...overrides,
  } as Step;
}

function resetStore() {
  useStrategyStore.setState({
    stepLifecycleById: {},
    undoStack: [],
    redoStack: [],
  });
}

describe("useStepSnapshot", () => {
  beforeEach(resetStore);

  it("defaults to idle with null values for a null step", () => {
    const { result } = renderHook(() => useStepSnapshot(null));
    expect(result.current.step).toBeNull();
    expect(result.current.lifecycleState).toBe("idle");
    expect(result.current.estimatedSize).toBeNull();
    expect(result.current.validationErrors).toBeNull();
    expect(result.current.isBusy).toBe(false);
    expect(result.current.isInvalid).toBe(false);
    expect(result.current.isFailed).toBe(false);
  });

  it("returns wire estimatedSize when no lifecycle context override", () => {
    const step = makeStep({ estimatedSize: 99 });
    const { result } = renderHook(() => useStepSnapshot(step));
    expect(result.current.estimatedSize).toBe(99);
  });

  it("lifecycle estimatedSize overrides wire when present", () => {
    const step = makeStep({ estimatedSize: 10 });
    useStrategyStore.getState().applyStepCounts({ s1: 500 });
    const { result } = renderHook(() => useStepSnapshot(step));
    expect(result.current.estimatedSize).toBe(500);
    expect(result.current.lifecycleState).toBe("complete");
  });

  it("surfaces invalid state and validation errors", () => {
    const step = makeStep();
    useStrategyStore.getState().applyStepValidationErrors({ s1: "Missing taxon" });
    const { result } = renderHook(() => useStepSnapshot(step));
    expect(result.current.isInvalid).toBe(true);
    expect(result.current.validationErrors?.general?.[0]).toBe("Missing taxon");
  });

  it("surfaces failed state with lastError", () => {
    const step = makeStep();
    const api = useStrategyStore.getState();
    api.dispatchStepEvent("s1", { type: "VALIDATE" });
    api.dispatchStepEvent("s1", { type: "VALIDATION_SUCCESS" });
    api.dispatchStepEvent("s1", { type: "RUN_COUNTS" });
    api.dispatchStepEvent("s1", { type: "RUN_ERROR", message: "500" });
    const { result } = renderHook(() => useStepSnapshot(step));
    expect(result.current.isFailed).toBe(true);
    expect(result.current.lastError).toBe("500");
  });

  it("isBusy true during validating / running", () => {
    const step = makeStep();
    const api = useStrategyStore.getState();
    api.initStepLifecycle("s1");
    api.dispatchStepEvent("s1", { type: "VALIDATE" });
    const { result, rerender } = renderHook(() => useStepSnapshot(step));
    expect(result.current.isBusy).toBe(true);
    api.dispatchStepEvent("s1", { type: "VALIDATION_SUCCESS" });
    rerender();
    expect(result.current.isBusy).toBe(false);
  });

  it("falls back to wire validation.errors when lifecycle has none", () => {
    const step = makeStep({
      validation: {
        level: "UNRUNNABLE",
        isValid: false,
        errors: { general: ["Server said no"], byKey: {} },
      },
    });
    const { result } = renderHook(() => useStepSnapshot(step));
    expect(result.current.validationErrors?.general?.[0]).toBe("Server said no");
  });
});

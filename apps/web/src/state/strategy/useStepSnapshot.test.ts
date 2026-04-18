/**
 * @vitest-environment jsdom
 */
import { describe, expect, it, beforeEach } from "vitest";
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
    strategy: null,
    stepsById: {},
    stepLifecycleById: {},
    undoStack: [],
    redoStack: [],
  });
}

describe("useStepSnapshot", () => {
  beforeEach(resetStore);

  it("defaults to idle with null values for an unknown step id", () => {
    const { result } = renderHook(() => useStepSnapshot("missing"));
    expect(result.current.step).toBeNull();
    expect(result.current.lifecycleState).toBe("idle");
    expect(result.current.estimatedSize).toBeNull();
    expect(result.current.validationErrors).toBeNull();
    expect(result.current.isBusy).toBe(false);
    expect(result.current.isInvalid).toBe(false);
    expect(result.current.isFailed).toBe(false);
  });

  it("returns wire estimatedSize when no lifecycle context override", () => {
    useStrategyStore.setState({
      stepsById: { s1: makeStep({ estimatedSize: 99 }) },
    });
    const { result } = renderHook(() => useStepSnapshot("s1"));
    expect(result.current.estimatedSize).toBe(99);
  });

  it("lifecycle estimatedSize overrides wire when present", () => {
    const api = useStrategyStore.getState();
    useStrategyStore.setState({
      stepsById: { s1: makeStep({ estimatedSize: 10 }) },
    });
    api.applyStepCounts({ s1: 500 });
    const { result } = renderHook(() => useStepSnapshot("s1"));
    expect(result.current.estimatedSize).toBe(500);
    expect(result.current.lifecycleState).toBe("complete");
  });

  it("surfaces invalid state and validation errors", () => {
    const api = useStrategyStore.getState();
    useStrategyStore.setState({ stepsById: { s1: makeStep() } });
    api.applyStepValidationErrors({ s1: "Missing taxon" });
    const { result } = renderHook(() => useStepSnapshot("s1"));
    expect(result.current.isInvalid).toBe(true);
    expect(result.current.validationErrors?.general?.[0]).toBe("Missing taxon");
  });

  it("surfaces failed state with lastError", () => {
    const api = useStrategyStore.getState();
    useStrategyStore.setState({ stepsById: { s1: makeStep() } });
    api.initStepLifecycle("s1", { state: "valid" });
    api.dispatchStepEvent("s1", { type: "RUN_COUNTS" });
    api.dispatchStepEvent("s1", { type: "RUN_ERROR", message: "500" });
    const { result } = renderHook(() => useStepSnapshot("s1"));
    expect(result.current.isFailed).toBe(true);
    expect(result.current.lastError).toBe("500");
  });

  it("isBusy true during validating / running", () => {
    const api = useStrategyStore.getState();
    useStrategyStore.setState({ stepsById: { s1: makeStep() } });
    api.initStepLifecycle("s1");
    api.dispatchStepEvent("s1", { type: "VALIDATE" });
    const { result, rerender } = renderHook(() => useStepSnapshot("s1"));
    expect(result.current.isBusy).toBe(true);
    api.dispatchStepEvent("s1", { type: "VALIDATION_SUCCESS" });
    rerender();
    expect(result.current.isBusy).toBe(false);
  });

  it("falls back to wire validation.errors when lifecycle has none", () => {
    useStrategyStore.setState({
      stepsById: {
        s1: makeStep({
          validation: {
            level: "UNRUNNABLE",
            isValid: false,
            errors: { general: ["Server said no"], byKey: {} },
          },
        }),
      },
    });
    const { result } = renderHook(() => useStepSnapshot("s1"));
    expect(result.current.validationErrors?.general?.[0]).toBe("Server said no");
  });
});

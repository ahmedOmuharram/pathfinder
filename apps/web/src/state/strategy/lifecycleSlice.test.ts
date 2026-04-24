import { describe, expect, it, beforeEach } from "vitest";
import { useStrategyStore } from "./store";

function resetStore() {
  useStrategyStore.setState({
    stepLifecycleById: {},
    undoStack: [],
    redoStack: [],
  });
}

describe("lifecycleSlice — initStepLifecycle", () => {
  beforeEach(resetStore);

  it("creates an idle lifecycle for a new step id", () => {
    useStrategyStore.getState().initStepLifecycle("s1");
    const snap = useStrategyStore.getState().getStepLifecycle("s1");
    expect(snap).not.toBeNull();
    expect(snap!.value).toBe("idle");
    expect(snap!.context.estimatedSize).toBeNull();
  });

  it("accepts a seed state and context", () => {
    useStrategyStore.getState().initStepLifecycle("s1", {
      state: "complete",
      context: { estimatedSize: 42 },
    });
    const snap = useStrategyStore.getState().getStepLifecycle("s1");
    expect(snap!.value).toBe("complete");
    expect(snap!.context.estimatedSize).toBe(42);
  });

  it("does not clobber an existing lifecycle", () => {
    useStrategyStore.getState().initStepLifecycle("s1", {
      state: "complete",
      context: { estimatedSize: 50 },
    });
    useStrategyStore.getState().initStepLifecycle("s1");
    const snap = useStrategyStore.getState().getStepLifecycle("s1");
    expect(snap!.value).toBe("complete");
    expect(snap!.context.estimatedSize).toBe(50);
  });
});

describe("lifecycleSlice — dispatchStepEvent", () => {
  beforeEach(resetStore);

  it("transitions a step through VALIDATE → VALIDATION_SUCCESS", () => {
    const api = useStrategyStore.getState();
    api.initStepLifecycle("s1");
    api.dispatchStepEvent("s1", { type: "VALIDATE" });
    expect(api.getStepLifecycle("s1")!.value).toBe("validating");
    api.dispatchStepEvent("s1", { type: "VALIDATION_SUCCESS", estimatedSize: 10 });
    const snap = useStrategyStore.getState().getStepLifecycle("s1");
    expect(snap!.value).toBe("valid");
    expect(snap!.context.estimatedSize).toBe(10);
  });

  it("auto-initializes a missing step lifecycle on dispatch", () => {
    useStrategyStore.getState().dispatchStepEvent("new-step", { type: "VALIDATE" });
    const snap = useStrategyStore.getState().getStepLifecycle("new-step");
    expect(snap!.value).toBe("validating");
  });

  it("transitions through RUN_COUNTS → COUNTS_READY", () => {
    const api = useStrategyStore.getState();
    api.initStepLifecycle("s1", { state: "valid" });
    api.dispatchStepEvent("s1", { type: "RUN_COUNTS" });
    expect(api.getStepLifecycle("s1")!.value).toBe("running");
    api.dispatchStepEvent("s1", { type: "COUNTS_READY", count: 500 });
    const snap = useStrategyStore.getState().getStepLifecycle("s1");
    expect(snap!.value).toBe("complete");
    expect(snap!.context.estimatedSize).toBe(500);
  });

  it("captures validation errors in context on VALIDATION_ERROR", () => {
    const api = useStrategyStore.getState();
    api.initStepLifecycle("s1");
    api.dispatchStepEvent("s1", { type: "VALIDATE" });
    api.dispatchStepEvent("s1", {
      type: "VALIDATION_ERROR",
      errors: { general: ["bad"], byKey: {} },
    });
    const snap = useStrategyStore.getState().getStepLifecycle("s1");
    expect(snap!.value).toBe("invalid");
    expect(snap!.context.validationErrors?.general?.[0]).toBe("bad");
  });
});

describe("lifecycleSlice — removeStepLifecycle", () => {
  beforeEach(resetStore);

  it("removes the lifecycle entry for a step id", () => {
    const api = useStrategyStore.getState();
    api.initStepLifecycle("s1");
    api.removeStepLifecycle("s1");
    expect(useStrategyStore.getState().getStepLifecycle("s1")).toBeNull();
  });
});

describe("lifecycleSlice — batch helpers", () => {
  beforeEach(resetStore);

  it("applyStepValidationErrors dispatches VALIDATION_ERROR/VALIDATION_SUCCESS per step", () => {
    const api = useStrategyStore.getState();
    api.initStepLifecycle("s1");
    api.initStepLifecycle("s2");
    api.dispatchStepEvent("s1", { type: "VALIDATE" });
    api.dispatchStepEvent("s2", { type: "VALIDATE" });
    api.applyStepValidationErrors({
      s1: "Missing taxon",
      s2: undefined,
    });
    const snap1 = useStrategyStore.getState().getStepLifecycle("s1");
    const snap2 = useStrategyStore.getState().getStepLifecycle("s2");
    expect(snap1!.value).toBe("invalid");
    expect(snap1!.context.validationErrors?.general?.[0]).toBe("Missing taxon");
    expect(snap2!.value).toBe("valid");
  });

  it("applyStepCounts dispatches RUN_COUNTS + COUNTS_READY per step", () => {
    const api = useStrategyStore.getState();
    api.initStepLifecycle("s1", { state: "valid" });
    api.initStepLifecycle("s2", { state: "valid" });
    api.applyStepCounts({ s1: 100, s2: null });
    const snap1 = useStrategyStore.getState().getStepLifecycle("s1");
    const snap2 = useStrategyStore.getState().getStepLifecycle("s2");
    expect(snap1!.value).toBe("complete");
    expect(snap1!.context.estimatedSize).toBe(100);
    expect(snap2!.value).toBe("complete");
    expect(snap2!.context.estimatedSize).toBeNull();
  });
});

describe("lifecycleSlice — clear resets everything", () => {
  beforeEach(resetStore);

  it("clear() removes all lifecycles", () => {
    const api = useStrategyStore.getState();
    api.initStepLifecycle("s1");
    api.initStepLifecycle("s2");
    api.clear();
    expect(Object.keys(useStrategyStore.getState().stepLifecycleById)).toHaveLength(0);
  });
});

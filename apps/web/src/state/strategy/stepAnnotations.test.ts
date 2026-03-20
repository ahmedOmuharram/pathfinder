/**
 * Tests for step annotation helpers — pure functions that apply
 * validation errors or result counts to the step map, extracted
 * from draftSlice for SRP.
 */

import { describe, expect, it } from "vitest";
import type { Step } from "@pathfinder/shared";
import { applyStepValidationErrors, applyStepCounts } from "./stepAnnotations";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeStep(overrides: Partial<Step> = {}): Step {
  return {
    id: "s1",
    displayName: "Step 1",
    searchName: "GenesByTaxon",
    recordType: "transcript",
    parameters: {},
    validationError: null,
    resultCount: null,
    ...overrides,
  } as Step;
}

// ---------------------------------------------------------------------------
// applyStepValidationErrors
// ---------------------------------------------------------------------------

describe("applyStepValidationErrors", () => {
  it("returns null when no changes are needed", () => {
    const stepsById: Record<string, Step> = {
      s1: makeStep({ validationError: null }),
    };
    const result = applyStepValidationErrors(stepsById, { s1: undefined });
    expect(result).toBeNull();
  });

  it("applies validation error to matching step", () => {
    const stepsById: Record<string, Step> = {
      s1: makeStep({ validationError: null }),
    };
    const result = applyStepValidationErrors(stepsById, { s1: "Bad param" });
    expect(result).not.toBeNull();
    expect(result!["s1"]!.validationError).toBe("Bad param");
  });

  it("clears validation error when set to undefined", () => {
    const stepsById: Record<string, Step> = {
      s1: makeStep({ validationError: "Old error" }),
    };
    const result = applyStepValidationErrors(stepsById, { s1: undefined });
    expect(result).not.toBeNull();
    expect(result!["s1"]!.validationError).toBeNull();
  });

  it("skips unknown step IDs", () => {
    const stepsById: Record<string, Step> = {
      s1: makeStep(),
    };
    const result = applyStepValidationErrors(stepsById, { s999: "Error" });
    expect(result).toBeNull();
  });

  it("handles multiple steps", () => {
    const stepsById: Record<string, Step> = {
      s1: makeStep({ id: "s1", validationError: null }),
      s2: makeStep({ id: "s2", validationError: null }),
    };
    const result = applyStepValidationErrors(stepsById, {
      s1: "Error A",
      s2: "Error B",
    });
    expect(result).not.toBeNull();
    expect(result!["s1"]!.validationError).toBe("Error A");
    expect(result!["s2"]!.validationError).toBe("Error B");
  });
});

// ---------------------------------------------------------------------------
// applyStepCounts
// ---------------------------------------------------------------------------

describe("applyStepCounts", () => {
  it("returns null when no changes are needed", () => {
    const stepsById: Record<string, Step> = {
      s1: makeStep({ resultCount: 42 }),
    };
    const result = applyStepCounts(stepsById, { s1: 42 });
    expect(result).toBeNull();
  });

  it("applies count to matching step", () => {
    const stepsById: Record<string, Step> = {
      s1: makeStep({ resultCount: null }),
    };
    const result = applyStepCounts(stepsById, { s1: 100 });
    expect(result).not.toBeNull();
    expect(result!["s1"]!.resultCount).toBe(100);
  });

  it("sets count to null", () => {
    const stepsById: Record<string, Step> = {
      s1: makeStep({ resultCount: 42 }),
    };
    const result = applyStepCounts(stepsById, { s1: null });
    expect(result).not.toBeNull();
    expect(result!["s1"]!.resultCount).toBeNull();
  });

  it("skips unknown step IDs", () => {
    const stepsById: Record<string, Step> = {
      s1: makeStep(),
    };
    const result = applyStepCounts(stepsById, { s999: 10 });
    expect(result).toBeNull();
  });

  it("coerces undefined to null", () => {
    const stepsById: Record<string, Step> = {
      s1: makeStep({ resultCount: 42 }),
    };
    const result = applyStepCounts(stepsById, { s1: undefined });
    expect(result).not.toBeNull();
    expect(result!["s1"]!.resultCount).toBeNull();
  });
});

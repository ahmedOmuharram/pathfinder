import { describe, expect, it } from "vitest";
import {
  findCombineRecordTypeMismatch,
  getCombineMismatchGroups,
  getRootStepId,
  getRootSteps,
  resolveRecordType,
  validateStrategySteps,
} from "./validate";
import type { Step } from "./types";

describe("core/strategyGraph/validate", () => {
  it("computes root steps and rootStepId", () => {
    const steps: Step[] = [
      { id: "a", displayName: "A", searchName: "q1", recordType: "gene" },
      {
        id: "b",
        displayName: "B",
        searchName: "q2",
        recordType: "gene",
        primaryInputStepId: "a",
      },
    ];
    expect(getRootSteps(steps).map((s) => s.id)).toEqual(["b"]);
    expect(getRootStepId(steps)).toBe("b");
  });

  it("returns null rootStepId when multiple roots exist", () => {
    const steps: Step[] = [
      { id: "a", displayName: "A", searchName: "q1", recordType: "gene" },
      { id: "b", displayName: "B", searchName: "q2", recordType: "gene" },
    ];
    expect(
      getRootSteps(steps)
        .map((s) => s.id)
        .sort(),
    ).toEqual(["a", "b"]);
    expect(getRootStepId(steps)).toBeNull();
  });

  it("validates missing searchName for non-combine steps", () => {
    const steps: Step[] = [{ id: "a", displayName: "A", recordType: "gene" }];
    const errors = validateStrategySteps(steps);
    expect(
      errors.some((e) => e.code === "MISSING_SEARCH_NAME" && e.stepId === "a"),
    ).toBe(true);
  });

  it("validates invalid secondary input without primary input", () => {
    const steps: Step[] = [
      {
        id: "c",
        displayName: "C",
        searchName: "q",
        secondaryInputStepId: "x",
        recordType: "gene",
      },
    ];
    const errors = validateStrategySteps(steps);
    expect(errors.some((e) => e.code === "MISSING_INPUT" && e.stepId === "c")).toBe(
      true,
    );
  });

  it("validates combine invariants (operator + two inputs + colocate params)", () => {
    const steps: Step[] = [
      { id: "l", displayName: "L", searchName: "q1", recordType: "gene" },
      { id: "r", displayName: "R", searchName: "q2", recordType: "gene" },
      {
        id: "c",
        displayName: "C",
        primaryInputStepId: "l",
        secondaryInputStepId: "r",
        // missing operator
        recordType: "gene",
      },
    ];
    const errors = validateStrategySteps(steps);
    expect(errors.some((e) => e.code === "MISSING_OPERATOR" && e.stepId === "c")).toBe(
      true,
    );

    const colocate: Step = {
      id: "co",
      displayName: "Co",
      primaryInputStepId: "l",
      secondaryInputStepId: "r",
      operator: "COLOCATE",
      recordType: "gene",
    };
    const errors2 = validateStrategySteps([steps[0], steps[1], colocate]);
    expect(errors2.some((e) => e.code === "MISSING_INPUT" && e.stepId === "co")).toBe(
      true,
    );
  });

  it("flags unknown input step ids", () => {
    const steps: Step[] = [
      { id: "a", displayName: "A", searchName: "q1", recordType: "gene" },
      {
        id: "b",
        displayName: "B",
        searchName: "q2",
        recordType: "gene",
        primaryInputStepId: "missing",
      },
    ];
    const errors = validateStrategySteps(steps);
    expect(
      errors.some((e) => e.code === "UNKNOWN_STEP" && e.inputStepId === "missing"),
    ).toBe(true);
  });

  it("reports MULTIPLE_ROOTS when graph has multiple outputs", () => {
    const steps: Step[] = [
      { id: "a", displayName: "A", searchName: "q1", recordType: "gene" },
      { id: "b", displayName: "B", searchName: "q2", recordType: "gene" },
    ];
    const errors = validateStrategySteps(steps);
    expect(errors.some((e) => e.code === "MULTIPLE_ROOTS")).toBe(true);
  });

  it("resolves record types through transform/combine and detects mismatch", () => {
    const steps: Step[] = [
      { id: "left", displayName: "Left", searchName: "q1", recordType: "gene" },
      { id: "right", displayName: "Right", searchName: "q2", recordType: "genome" },
      {
        id: "combine",
        displayName: "Combine",
        primaryInputStepId: "left",
        secondaryInputStepId: "right",
        operator: "UNION",
      },
    ];
    const map = new Map(steps.map((s) => [s.id, s]));
    expect(resolveRecordType("combine", map)).toBe("__mismatch__");

    const mismatch = findCombineRecordTypeMismatch(steps);
    expect(mismatch?.stepId).toBe("combine");

    const groups = getCombineMismatchGroups(steps);
    expect(groups).toHaveLength(1);
    expect(groups[0]?.ids.has("combine")).toBe(true);
  });
});

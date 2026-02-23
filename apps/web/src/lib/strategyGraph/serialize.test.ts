import { describe, expect, it } from "vitest";
import { serializeStrategyPlan } from "./serialize";
import type { Step, Strategy } from "./types";

describe("core/strategyGraph/serialize", () => {
  it("returns null when graph has multiple roots (multiple outputs)", () => {
    const stepsById: Record<string, Step> = {
      a: { id: "a", displayName: "A", searchName: "q1", recordType: "gene" },
      b: { id: "b", displayName: "B", searchName: "q2", recordType: "gene" },
    };
    const res = serializeStrategyPlan(stepsById, {
      id: "s",
      name: "S",
      siteId: "plasmodb",
      recordType: "gene",
      steps: Object.values(stepsById),
      rootStepId: null,
      createdAt: "t",
      updatedAt: "t",
    });
    expect(res).toBeNull();
  });

  it("serializes a linear plan and sanitizes @@fake@@ parameters", () => {
    const stepsById: Record<string, Step> = {
      a: {
        id: "a",
        displayName: "A",
        searchName: "q1",
        recordType: "gene",
        parameters: { ok: 1, fake: "@@fake@@", arr: ["x", "@@fake@@"] },
      },
      b: {
        id: "b",
        displayName: "B",
        searchName: "q2",
        recordType: "gene",
        primaryInputStepId: "a",
        parameters: { ok: true },
      },
    };

    const strategy: Strategy = {
      id: "s1",
      name: "My Strategy",
      description: "desc",
      siteId: "plasmodb",
      recordType: "gene",
      steps: Object.values(stepsById),
      rootStepId: "b",
      createdAt: "t",
      updatedAt: "t",
    };

    const res = serializeStrategyPlan(stepsById, strategy);
    expect(res?.plan.root.id).toBe("b");
    expect(res?.plan.root.primaryInput?.id).toBe("a");
    // Any params containing the UI-only @@fake@@ sentinel are removed.
    expect(res?.plan.root.primaryInput?.parameters).toEqual({ ok: 1 });
    expect((res?.plan.root.primaryInput?.parameters as any)?.fake).toBeUndefined();
    expect((res?.plan.root.primaryInput?.parameters as any)?.arr).toBeUndefined();
    expect(res?.plan.metadata?.name).toBe("My Strategy");
    expect(res?.plan.metadata?.description).toBe("desc");
  });

  it("serializes combine nodes with __combine__ searchName and requires operator", () => {
    const stepsById: Record<string, Step> = {
      l: { id: "l", displayName: "L", searchName: "q1", recordType: "gene" },
      r: { id: "r", displayName: "R", searchName: "q2", recordType: "gene" },
      c: {
        id: "c",
        displayName: "C",
        primaryInputStepId: "l",
        secondaryInputStepId: "r",
        operator: "UNION",
        recordType: "gene",
      },
    };

    const strategy: Strategy = {
      id: "s1",
      name: "S",
      siteId: "plasmodb",
      recordType: "gene",
      steps: Object.values(stepsById),
      rootStepId: "c",
      createdAt: "t",
      updatedAt: "t",
    };

    const res = serializeStrategyPlan(stepsById, strategy);
    expect(res?.plan.root.searchName).toBe("__combine__");
    expect(res?.plan.root.operator).toBe("UNION");

    const broken = { ...stepsById, c: { ...stepsById.c, operator: undefined } };
    const res2 = serializeStrategyPlan(broken, strategy);
    expect(res2).toBeNull();
  });
});

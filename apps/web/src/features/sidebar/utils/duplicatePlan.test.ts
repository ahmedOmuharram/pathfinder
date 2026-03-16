import { describe, expect, it, vi } from "vitest";
import type { Strategy } from "@pathfinder/shared";
import type { SerializedStrategyPlan } from "@/lib/strategyGraph/serialize";
import { AppError } from "@/lib/errors/AppError";

vi.mock("@/lib/strategyGraph", () => ({
  serializeStrategyPlan: vi.fn(),
}));

import { serializeStrategyPlan } from "@/lib/strategyGraph";
import { buildDuplicatePlan } from "@/features/sidebar/utils/duplicatePlan";

const base: Strategy = {
  id: "s1",
  steps: [{ id: "a", displayName: "A" }],
  name: "X",
  description: "",
  siteId: "s",
  recordType: null,
  rootStepId: null,
  isSaved: false,
  createdAt: "t",
  updatedAt: "t",
};

describe("buildDuplicatePlan", () => {
  it("throws AppError when serialization fails", () => {
    vi.mocked(serializeStrategyPlan).mockReturnValueOnce(null);
    expect(() =>
      buildDuplicatePlan({ baseStrategy: base, name: "N", description: "D" }),
    ).toThrowError(AppError);
  });

  it("returns serialized plan on success", () => {
    vi.mocked(serializeStrategyPlan).mockReturnValueOnce({
      plan: { recordType: "gene", root: { searchName: "s" } },
      name: "N",
      recordType: "gene",
    } satisfies SerializedStrategyPlan);
    const plan = buildDuplicatePlan({
      baseStrategy: base,
      name: "N",
      description: "D",
    });
    expect(plan).toMatchObject({ recordType: "gene" });
  });
});

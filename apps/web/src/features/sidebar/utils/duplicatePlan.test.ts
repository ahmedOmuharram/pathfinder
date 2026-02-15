import { describe, expect, it, vi } from "vitest";
import { AppError } from "@/shared/errors/AppError";

vi.mock("@/core/strategyGraph", () => ({
  serializeStrategyPlan: vi.fn(),
}));

import { serializeStrategyPlan } from "@/core/strategyGraph";
import { buildDuplicatePlan } from "@/features/sidebar/utils/duplicatePlan";

describe("buildDuplicatePlan", () => {
  it("throws AppError when serialization fails", () => {
    vi.mocked(serializeStrategyPlan).mockReturnValueOnce(null as any);
    const base: any = { steps: [{ id: "a" }], name: "X", description: "", siteId: "s" };
    expect(() =>
      buildDuplicatePlan({ baseStrategy: base, name: "N", description: "D" }),
    ).toThrowError(AppError);
  });

  it("returns serialized plan on success", () => {
    vi.mocked(serializeStrategyPlan).mockReturnValueOnce({
      plan: { recordType: "gene", root: { searchName: "s" } },
    } as any);
    const base: any = { steps: [{ id: "a" }], name: "X", description: "", siteId: "s" };
    const plan = buildDuplicatePlan({
      baseStrategy: base,
      name: "N",
      description: "D",
    });
    expect(plan).toMatchObject({ recordType: "gene" });
  });
});

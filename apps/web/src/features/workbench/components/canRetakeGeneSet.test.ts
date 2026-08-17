import { describe, expect, it } from "vitest";

import { canRetakeGeneSet } from "./canRetakeGeneSet";

describe("canRetakeGeneSet", () => {
  it("offers a re-take for a set taken from a strategy", () => {
    // Its membership is frozen, so following the strategy again is the only
    // way to pick up an edit.
    expect(canRetakeGeneSet({ wdkStrategyId: 330531493 })).toBe(true);
  });

  it("does not offer one for a pasted list", () => {
    expect(canRetakeGeneSet({ wdkStrategyId: null })).toBe(false);
  });

  it("does not offer one when the field is absent", () => {
    expect(canRetakeGeneSet({})).toBe(false);
  });
});

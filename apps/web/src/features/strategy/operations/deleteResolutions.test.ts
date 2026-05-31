import { describe, expect, test } from "vitest";
import type { Step } from "@pathfinder/shared";
import { computeDeleteChoices, isAmbiguousDelete } from "./deleteResolutions";

const step = (
  id: string,
  primary?: string,
  secondary?: string,
  kind: "search" | "transform" | "combine" = "search",
): Step =>
  ({
    id,
    kind,
    displayName: id,
    primaryInputStepId: primary,
    secondaryInputStepId: secondary,
    isBuilt: false,
    isFiltered: false,
  }) as Step;

describe("computeDeleteChoices", () => {
  test("sole leaf: only delete-strategy choice", () => {
    const steps = [step("a")];
    const choices = computeDeleteChoices(steps, "a");
    expect(choices.map((c) => c.resolution)).toEqual(["delete-strategy"]);
    expect(choices[0]!.willDelete).toEqual(["a"]);
    expect(choices[0]!.isDefault).toBe(true);
  });

  test("leaf of root combine: collapse-combine (default), orphan-sibling, delete-subtree", () => {
    const steps = [step("a"), step("b"), step("c", "a", "b", "combine")];
    const choices = computeDeleteChoices(steps, "a");
    const tokens = choices.map((c) => c.resolution);
    expect(tokens).toEqual(
      expect.arrayContaining(["collapse-combine", "orphan-sibling", "delete-subtree"]),
    );
    const def = choices.find((c) => c.isDefault);
    expect(def?.resolution).toBe("collapse-combine");
    const collapse = choices.find((c) => c.resolution === "collapse-combine")!;
    expect(collapse.willDelete.sort()).toEqual(["a", "c"]);
    const orphan = choices.find((c) => c.resolution === "orphan-sibling")!;
    expect(orphan.willDelete).toEqual(["a"]);
    expect(orphan.willOrphan.sort()).toEqual(["b", "c"]);
  });

  test("leaf of nested combine: sibling reconnects to grandparent", () => {
    const steps = [
      step("A"),
      step("B"),
      step("D"),
      step("C", "A", "B", "combine"),
      step("R", "C", "D", "combine"),
    ];
    const choices = computeDeleteChoices(steps, "A");
    const collapse = choices.find((c) => c.resolution === "collapse-combine")!;
    expect(collapse.willDelete.sort()).toEqual(["A", "C"]);
    expect(collapse.willOrphan).toEqual([]);
  });

  test("root combine: promote-primary, delete-strategy", () => {
    const steps = [step("a"), step("b"), step("c", "a", "b", "combine")];
    const choices = computeDeleteChoices(steps, "c");
    const tokens = choices.map((c) => c.resolution);
    expect(tokens).toEqual(
      expect.arrayContaining(["promote-primary", "delete-strategy"]),
    );
    const promote = choices.find((c) => c.resolution === "promote-primary")!;
    expect(promote.willDelete.sort()).toEqual(["b", "c"]);
    expect(promote.isDefault).toBe(true);
  });

  test("transform in middle: bypass-only choice (token: collapse-combine)", () => {
    const steps = [step("a"), step("t", "a", undefined, "transform"), step("r", "t")];
    const choices = computeDeleteChoices(steps, "t");
    expect(choices.map((c) => c.resolution)).toEqual(["collapse-combine"]);
    expect(choices[0]!.willDelete).toEqual(["t"]);
  });

  test("step whose parent is a transform: cascade subtree + transform", () => {
    const steps = [step("a"), step("t", "a", undefined, "transform"), step("r", "t")];
    const choices = computeDeleteChoices(steps, "a");
    expect(choices.map((c) => c.resolution)).toEqual(["delete-subtree"]);
    expect(choices[0]!.willDelete.sort()).toEqual(["a", "t"]);
  });

  test("returns [] for unknown step id", () => {
    expect(computeDeleteChoices([step("a")], "missing")).toEqual([]);
  });
});

describe("isAmbiguousDelete", () => {
  test("true when more than one choice", () => {
    const steps = [step("a"), step("b"), step("c", "a", "b", "combine")];
    expect(isAmbiguousDelete(steps, "a")).toBe(true);
  });
  test("false when only one choice", () => {
    expect(isAmbiguousDelete([step("a")], "a")).toBe(false);
  });
  test("false for unknown id", () => {
    expect(isAmbiguousDelete([step("a")], "missing")).toBe(false);
  });
});

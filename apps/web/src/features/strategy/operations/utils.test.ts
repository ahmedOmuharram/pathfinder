import { describe, expect, test } from "vitest";
import type { Step } from "@pathfinder/shared";
import {
  buildIndex,
  findParent,
  walkSubtreeIds,
  getRootIds,
  isReachableFromAnyRoot,
  subtreeSize,
} from "./utils";

const step = (
  id: string,
  primary?: string,
  secondary?: string,
  kind: "search" | "transform" | "combine" = "search",
): Step => ({
  id,
  kind,
  displayName: id,
  primaryInputStepId: primary ?? null,
  secondaryInputStepId: secondary ?? null,
  isFiltered: false,
});

describe("buildIndex", () => {
  test("indexes by id and counts incoming refs", () => {
    const steps = [step("a"), step("b"), step("c", "a", "b", "combine")];
    const idx = buildIndex(steps);
    expect(idx.byId.get("a")).toBe(steps[0]);
    expect(idx.consumerOf.get("a")).toEqual({ stepId: "c", slot: "primary" });
    expect(idx.consumerOf.get("b")).toEqual({ stepId: "c", slot: "secondary" });
    expect(idx.consumerOf.has("c")).toBe(false);
  });
});

describe("findParent", () => {
  test("returns parent and slot for primary input", () => {
    const steps = [step("a"), step("b"), step("c", "a", "b", "combine")];
    expect(findParent(steps, "a")).toEqual({ parent: steps[2], slot: "primary" });
  });
  test("returns parent and slot for secondary input", () => {
    const steps = [step("a"), step("b"), step("c", "a", "b", "combine")];
    expect(findParent(steps, "b")).toEqual({ parent: steps[2], slot: "secondary" });
  });
  test("returns null for root", () => {
    const steps = [step("a"), step("b"), step("c", "a", "b", "combine")];
    expect(findParent(steps, "c")).toBeNull();
  });
  test("returns null for unknown id", () => {
    expect(findParent([step("a")], "missing")).toBeNull();
  });
});

describe("walkSubtreeIds", () => {
  test("returns ids in subtree rooted at given id", () => {
    const steps = [
      step("a"),
      step("b"),
      step("c", "a", "b", "combine"),
      step("d", "c", undefined, "transform"),
    ];
    expect(walkSubtreeIds(steps, "c").sort()).toEqual(["a", "b", "c"]);
  });
  test("includes downstream when walking from a transform parent", () => {
    const steps = [
      step("a"),
      step("b"),
      step("c", "a", "b", "combine"),
      step("d", "c", undefined, "transform"),
    ];
    expect(walkSubtreeIds(steps, "d").sort()).toEqual(["a", "b", "c", "d"]);
  });
  test("singleton for leaf", () => {
    const steps = [step("a"), step("b")];
    expect(walkSubtreeIds(steps, "a")).toEqual(["a"]);
  });
  test("empty for unknown id", () => {
    expect(walkSubtreeIds([step("a")], "missing")).toEqual([]);
  });
});

describe("getRootIds", () => {
  test("returns the unique root", () => {
    const steps = [step("a"), step("b"), step("c", "a", "b", "combine")];
    expect(getRootIds(steps)).toEqual(["c"]);
  });
  test("returns multiple roots when graph is disconnected", () => {
    const steps = [step("a"), step("b")];
    expect(getRootIds(steps).sort()).toEqual(["a", "b"]);
  });
  test("returns [] for empty steps", () => {
    expect(getRootIds([])).toEqual([]);
  });
});

describe("subtreeSize", () => {
  test("counts unique ids reachable upstream from id", () => {
    const steps = [step("a"), step("b"), step("c", "a", "b", "combine")];
    expect(subtreeSize(steps, "c")).toBe(3);
    expect(subtreeSize(steps, "a")).toBe(1);
  });
});

describe("isReachableFromAnyRoot", () => {
  test("true for connected component members", () => {
    const steps = [step("a"), step("b"), step("c", "a", "b", "combine")];
    expect(isReachableFromAnyRoot(steps, "a", new Set(["c"]))).toBe(true);
  });
  test("false for orphan when given empty root set", () => {
    const steps = [step("a"), step("b")];
    expect(isReachableFromAnyRoot(steps, "a", new Set())).toBe(false);
  });
});

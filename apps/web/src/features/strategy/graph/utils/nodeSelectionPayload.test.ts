import { describe, expect, test } from "vitest";
import { buildNodeSelectionPayload } from "@/features/strategy/graph/utils/nodeSelectionPayload";
import type { StrategyWithMeta } from "@/features/strategy/types";

describe("buildNodeSelectionPayload", () => {
  test("includes selected node(s) plus one-hop context (inputs + parents of selected inputs)", () => {
    const strategy = {
      id: "s1",
      steps: [
        { id: "a", kind: "search", displayName: "A" },
        { id: "b", kind: "transform", displayName: "B", primaryInputStepId: "a" },
        {
          id: "c",
          kind: "combine",
          displayName: "C",
          primaryInputStepId: "b",
          secondaryInputStepId: "a",
          operator: "UNION",
        },
      ],
    } as unknown as StrategyWithMeta;

    const payload = buildNodeSelectionPayload(strategy, ["b"]);
    expect(payload.graphId).toBe("s1");
    expect(payload.selectedNodeIds).toEqual(["b"]);
    expect(new Set(payload.contextNodeIds)).toEqual(new Set(["b", "a", "c"]));

    const nodeById = new Map(payload.nodes.map((n) => [n.id, n]));
    expect(nodeById.get("b")?.selected).toBe(true);
    expect(nodeById.get("a")?.selected).toBe(false);
    expect(nodeById.get("c")?.selected).toBe(false);
    expect(payload.edges).toEqual(
      expect.arrayContaining([
        { sourceId: "a", targetId: "b", kind: "primary" },
        { sourceId: "b", targetId: "c", kind: "primary" },
        { sourceId: "a", targetId: "c", kind: "secondary" },
      ]),
    );
  });
});

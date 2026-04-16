import { describe, it, expect } from "vitest";
import { layoutCheckpointTree } from "./layoutCheckpointTree";
import type { CheckpointNode } from "@pathfinder/shared/generated/types/CheckpointNode";

function makeCheckpoint(
  overrides: Partial<CheckpointNode> & Pick<CheckpointNode, "checkpointId" | "parentCheckpointId" | "step" | "source">,
): CheckpointNode {
  return {
    threadId: "t1",
    node: null,
    createdAt: "",
    ...overrides,
  };
}

const sampleNodes: CheckpointNode[] = [
  makeCheckpoint({ checkpointId: "cp0", parentCheckpointId: null, step: 0, node: "supervisor", source: "input" }),
  makeCheckpoint({ checkpointId: "cp1", parentCheckpointId: "cp0", step: 1, node: "scoping", source: "loop" }),
  makeCheckpoint({ checkpointId: "cp2", parentCheckpointId: "cp1", step: 2, node: "discovery", source: "loop" }),
  makeCheckpoint({ checkpointId: "cp3", parentCheckpointId: "cp1", step: 2, node: "scoping", source: "fork" }),
];

describe("layoutCheckpointTree", () => {
  it("computes positions for all nodes", async () => {
    const { nodes, edges } = await layoutCheckpointTree(sampleNodes);
    expect(nodes).toHaveLength(4);
    expect(edges).toHaveLength(3);
    for (const n of nodes) {
      expect(n.position.x).toBeTypeOf("number");
      expect(n.position.y).toBeTypeOf("number");
    }
  });

  it("fork siblings share y, differ in x", async () => {
    const { nodes } = await layoutCheckpointTree(sampleNodes);
    const cp2 = nodes.find((n) => n.id === "cp2");
    const cp3 = nodes.find((n) => n.id === "cp3");
    expect(cp2).toBeDefined();
    expect(cp3).toBeDefined();
    expect(cp2!.position.y).toBeCloseTo(cp3!.position.y, 0);
    expect(cp2!.position.x).not.toBe(cp3!.position.x);
  });

  it("preserves checkpoint data on each node", async () => {
    const { nodes } = await layoutCheckpointTree(sampleNodes);
    const cp1 = nodes.find((n) => n.id === "cp1");
    expect(cp1).toBeDefined();
    expect(cp1!.data).toMatchObject({
      checkpointId: "cp1",
      node: "scoping",
      source: "loop",
      step: 1,
    });
  });

  it("returns empty graph for empty input", async () => {
    const { nodes, edges } = await layoutCheckpointTree([]);
    expect(nodes).toHaveLength(0);
    expect(edges).toHaveLength(0);
  });

  it("handles single root node", async () => {
    const single = [
      makeCheckpoint({ checkpointId: "root", parentCheckpointId: null, step: 0, source: "input" }),
    ];
    const { nodes, edges } = await layoutCheckpointTree(single);
    expect(nodes).toHaveLength(1);
    expect(edges).toHaveLength(0);
  });

  it("uses checkpointNode as the node type", async () => {
    const { nodes } = await layoutCheckpointTree(sampleNodes);
    for (const n of nodes) {
      expect(n.type).toBe("checkpointNode");
    }
  });

  it("creates edges from parent to child", async () => {
    const { edges } = await layoutCheckpointTree(sampleNodes);
    const edge01 = edges.find((e) => e.source === "cp0" && e.target === "cp1");
    const edge12 = edges.find((e) => e.source === "cp1" && e.target === "cp2");
    const edge13 = edges.find((e) => e.source === "cp1" && e.target === "cp3");
    expect(edge01).toBeDefined();
    expect(edge12).toBeDefined();
    expect(edge13).toBeDefined();
  });
});

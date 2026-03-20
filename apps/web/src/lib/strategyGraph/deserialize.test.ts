import { describe, expect, test } from "vitest";
import { deserializeStrategyToGraph } from "@/lib/strategyGraph/deserialize";
import type { Strategy } from "@pathfinder/shared";

describe("deserializeStrategyToGraph", () => {
  test("returns empty graph for null/empty strategy", () => {
    expect(deserializeStrategyToGraph(null)).toEqual({ nodes: [], edges: [] });
    expect(deserializeStrategyToGraph({ steps: [] } as unknown as Strategy)).toEqual({
      nodes: [],
      edges: [],
    });
  });

  test("creates nodes + primary edge and sets connection affordances", () => {
    const strategy = {
      id: "s1",
      steps: [
        { id: "a", displayName: "A" },
        { id: "b", displayName: "B", primaryInputStepId: "a" },
      ],
    } as unknown as Strategy;

    const { nodes, edges } = deserializeStrategyToGraph(strategy);
    expect(nodes.map((n) => n.id).sort()).toEqual(["a", "b"]);
    expect(edges).toHaveLength(1);
    expect(edges[0]!).toMatchObject({
      id: "a-b-primary",
      source: "a",
      target: "b",
      targetHandle: "left",
    });

    const nodeById = new Map(nodes.map((n) => [n.id, n]));
    // Single root (b) => output handles are hidden for all nodes.
    expect(nodeById.get("a")?.data?.showOutputHandle).toBe(false);
    expect(nodeById.get("b")?.data?.showOutputHandle).toBe(false);
    // b has its primary input already => primary slot should not be shown.
    expect(nodeById.get("b")?.data?.showPrimaryInputHandle).toBe(false);
  });

  test("shows output handles when there are multiple roots", () => {
    const strategy = {
      id: "s2",
      steps: [
        { id: "a", displayName: "A" },
        { id: "b", displayName: "B" },
      ],
    } as unknown as Strategy;

    const { nodes } = deserializeStrategyToGraph(strategy);
    const nodeById = new Map(nodes.map((n) => [n.id, n]));
    expect(nodeById.get("a")?.data?.showOutputHandle).toBe(true);
    expect(nodeById.get("b")?.data?.showOutputHandle).toBe(true);
  });

  test("combine creates primary/secondary edges with L/R labels and hides filled input handles", () => {
    const strategy = {
      id: "s4",
      steps: [
        { id: "left", displayName: "Left" },
        { id: "right", displayName: "Right" },
        {
          id: "comb",
          displayName: "Combine",
          primaryInputStepId: "left",
          secondaryInputStepId: "right",
          operator: "UNION",
        },
      ],
    } as unknown as Strategy;

    const { nodes, edges } = deserializeStrategyToGraph(strategy);
    expect(edges).toHaveLength(2);
    expect(edges).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: "left-comb-primary",
          source: "left",
          target: "comb",
          targetHandle: "left",
          label: "L",
        }),
        expect.objectContaining({
          id: "right-comb-secondary",
          source: "right",
          target: "comb",
          targetHandle: "left-secondary",
          label: "R",
        }),
      ]),
    );

    const comb = nodes.find((n) => n.id === "comb");
    expect(comb?.data?.showPrimaryInputHandle).toBe(false);
    expect(comb?.data?.showSecondaryInputHandle).toBe(false);
  });

  test("combine with missing secondary input shows secondary input handle affordance", () => {
    const strategy = {
      id: "s5",
      steps: [
        { id: "left", displayName: "Left" },
        {
          id: "comb",
          displayName: "Combine",
          kind: "combine",
          primaryInputStepId: "left",
          operator: "UNION",
        },
      ],
    } as unknown as Strategy;

    const { nodes, edges } = deserializeStrategyToGraph(strategy);
    // Only primary edge exists.
    expect(edges).toHaveLength(1);
    const comb = nodes.find((n) => n.id === "comb");
    expect(comb?.data?.showPrimaryInputHandle).toBe(false);
    expect(comb?.data?.showSecondaryInputHandle).toBe(true);
  });

  test("preserves existing positions when provided; forceRelayout overrides", () => {
    const strategy = {
      id: "s3",
      steps: [
        { id: "a", displayName: "A" },
        { id: "b", displayName: "B" },
      ],
    } as unknown as Strategy;

    const existingPositions = new Map<string, { x: number; y: number }>([
      ["a", { x: 100, y: 200 }],
    ]);

    const preserved = deserializeStrategyToGraph(
      strategy,
      undefined,
      undefined,
      undefined,
      undefined,
      {
        existingPositions,
      },
    );
    const posA = preserved.nodes.find((n) => n.id === "a")?.position;
    expect(posA).toEqual({ x: 100, y: 200 });

    const relaid = deserializeStrategyToGraph(
      strategy,
      undefined,
      undefined,
      undefined,
      undefined,
      {
        existingPositions,
        forceRelayout: true,
      },
    );
    const posA2 = relaid.nodes.find((n) => n.id === "a")?.position;
    expect(posA2).toBeTruthy();
    expect(posA2).not.toEqual({ x: 100, y: 200 });
  });

  test("passes unsavedStepIds to node data as isUnsaved flag", () => {
    const strategy = {
      id: "s6",
      steps: [
        { id: "a", displayName: "A" },
        { id: "b", displayName: "B" },
      ],
    } as unknown as Strategy;

    const unsaved = new Set(["b"]);
    const { nodes } = deserializeStrategyToGraph(
      strategy,
      undefined,
      undefined,
      undefined,
      unsaved,
    );
    const nodeById = new Map(nodes.map((n) => [n.id, n]));
    expect(nodeById.get("a")?.data?.isUnsaved).toBe(false);
    expect(nodeById.get("b")?.data?.isUnsaved).toBe(true);
  });

  test("skips edges for primary/secondary inputs that reference missing steps", () => {
    const strategy = {
      id: "s7",
      steps: [{ id: "a", displayName: "A", primaryInputStepId: "missing" }],
    } as unknown as Strategy;

    const { nodes, edges } = deserializeStrategyToGraph(strategy);
    expect(nodes).toHaveLength(1);
    expect(edges).toHaveLength(0);
  });

  test("primary edge does not get L label when step has no secondary input", () => {
    const strategy = {
      id: "s8",
      steps: [
        { id: "a", displayName: "A" },
        { id: "b", displayName: "B", primaryInputStepId: "a" },
      ],
    } as unknown as Strategy;

    const { edges } = deserializeStrategyToGraph(strategy);
    expect(edges).toHaveLength(1);
    expect(edges[0]!.label).toBeUndefined();
  });

  test("all nodes have type='step' and correct source/target positions", () => {
    const strategy = {
      id: "s9",
      steps: [{ id: "a", displayName: "A" }],
    } as unknown as Strategy;

    const { nodes } = deserializeStrategyToGraph(strategy);
    expect(nodes[0]!.type).toBe("step");
    expect(nodes[0]!.sourcePosition).toBe("right");
    expect(nodes[0]!.targetPosition).toBe("left");
  });

  test("passes callback functions into node data", () => {
    const strategy = {
      id: "s10",
      steps: [{ id: "a", displayName: "A" }],
    } as unknown as Strategy;

    const onOperatorChange = () => {};
    const onAddToChat = () => {};
    const onOpenDetails = () => {};

    const { nodes } = deserializeStrategyToGraph(
      strategy,
      onOperatorChange,
      onAddToChat,
      onOpenDetails,
    );
    expect(nodes[0]!.data.onOperatorChange).toBe(onOperatorChange);
    expect(nodes[0]!.data.onAddToChat).toBe(onAddToChat);
    expect(nodes[0]!.data.onOpenDetails).toBe(onOpenDetails);
  });

  test("transform node with missing primary input shows primary input handle", () => {
    const strategy = {
      id: "s11",
      steps: [{ id: "t", displayName: "T", kind: "transform" }],
    } as unknown as Strategy;

    const { nodes } = deserializeStrategyToGraph(strategy);
    const tNode = nodes.find((n) => n.id === "t");
    expect(tNode?.data?.showPrimaryInputHandle).toBe(true);
    expect(tNode?.data?.showSecondaryInputHandle).toBe(false);
  });

  test("secondary edge always gets R label", () => {
    const strategy = {
      id: "s12",
      steps: [
        { id: "a", displayName: "A" },
        { id: "b", displayName: "B" },
        {
          id: "c",
          displayName: "C",
          primaryInputStepId: "a",
          secondaryInputStepId: "b",
          operator: "UNION",
        },
      ],
    } as unknown as Strategy;

    const { edges } = deserializeStrategyToGraph(strategy);
    const secondaryEdge = edges.find((e) => e.id.endsWith("-secondary"));
    expect(secondaryEdge?.label).toBe("R");
    expect(secondaryEdge?.targetHandle).toBe("left-secondary");
  });

  test("isUnsaved defaults to false when unsavedStepIds is not provided", () => {
    const strategy = {
      id: "s13",
      steps: [{ id: "a", displayName: "A" }],
    } as unknown as Strategy;

    const { nodes } = deserializeStrategyToGraph(strategy);
    expect(nodes[0]!.data.isUnsaved).toBe(false);
  });
});

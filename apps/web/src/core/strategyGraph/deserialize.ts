import dagre from "dagre";
import type { Edge, Node } from "reactflow";
import { MarkerType, Position } from "reactflow";
import type { Step, Strategy } from "./types";
import { inferStepKind } from "./kind";

type ExistingPositions = Map<string, { x: number; y: number }>;
type DeserializeOptions = {
  /**
   * When provided, we preserve existing node positions for unchanged nodes.
   * New nodes (not present in this map) get a dagre-derived position.
   */
  existingPositions?: ExistingPositions;
  /**
   * If true, ignore existingPositions and re-layout all nodes with dagre.
   */
  forceRelayout?: boolean;
};

export function deserializeStrategyToGraph(
  strategy: Strategy | null,
  onOperatorChange?: (stepId: string, operator: string) => void,
  onAddToChat?: (stepId: string) => void,
  onOpenDetails?: (stepId: string) => void,
  unsavedStepIds?: Set<string>,
  options?: DeserializeOptions,
): { nodes: Node[]; edges: Edge[] } {
  if (!strategy || strategy.steps.length === 0) {
    return { nodes: [], edges: [] };
  }

  const nodes: Node[] = [];
  const edges: Edge[] = [];
  const stepMap = new Map<string, Step>();
  const usedAsInputCount = new Map<string, number>();

  for (const step of strategy.steps) {
    stepMap.set(step.id, step);
  }
  for (const step of strategy.steps) {
    if (step.primaryInputStepId) {
      usedAsInputCount.set(
        step.primaryInputStepId,
        (usedAsInputCount.get(step.primaryInputStepId) ?? 0) + 1,
      );
    }
    if (step.secondaryInputStepId) {
      usedAsInputCount.set(
        step.secondaryInputStepId,
        (usedAsInputCount.get(step.secondaryInputStepId) ?? 0) + 1,
      );
    }
  }
  const rootStepIds = strategy.steps
    .map((s) => s.id)
    .filter((id) => (usedAsInputCount.get(id) ?? 0) === 0);
  const rootSet = new Set(rootStepIds);
  const shouldShowRootOutputs = rootStepIds.length !== 1;

  const gridSize = 28;
  const nodeWidth = 224;
  const nodeHeight = 112;
  const snap = (value: number) => Math.round(value / gridSize) * gridSize;

  const computeDagrePositions = (): Map<string, { x: number; y: number }> => {
    const layoutGraph = new dagre.graphlib.Graph();
    layoutGraph.setDefaultEdgeLabel(() => ({}));
    layoutGraph.setGraph({
      rankdir: "LR",
      nodesep: gridSize * 2,
      ranksep: gridSize * 4,
      marginx: gridSize * 2,
      marginy: gridSize * 2,
    });

    for (const step of strategy.steps) {
      layoutGraph.setNode(step.id, { width: nodeWidth, height: nodeHeight });
    }

    for (const step of strategy.steps) {
      if (step.primaryInputStepId && stepMap.has(step.primaryInputStepId)) {
        layoutGraph.setEdge(step.primaryInputStepId, step.id);
      }
      if (step.secondaryInputStepId && stepMap.has(step.secondaryInputStepId)) {
        layoutGraph.setEdge(step.secondaryInputStepId, step.id);
      }
    }

    dagre.layout(layoutGraph);

    const positions = new Map<string, { x: number; y: number }>();
    for (const step of strategy.steps) {
      const node = layoutGraph.node(step.id) as
        | { x: number; y: number; width: number; height: number }
        | undefined;
      if (!node) continue;
      positions.set(step.id, {
        x: node.x - node.width / 2,
        y: node.y - node.height / 2,
      });
    }
    return positions;
  };

  const dagrePositions = computeDagrePositions();

  const allPositions = Array.from(dagrePositions.values());
  if (allPositions.length === 0) {
    return { nodes: [], edges: [] };
  }
  const minX = Math.min(...allPositions.map((pos) => pos.x));
  const minY = Math.min(...allPositions.map((pos) => pos.y));
  const offsetX = minX < gridSize * 2 ? gridSize * 2 - minX : 0;
  const offsetY = minY < gridSize * 2 ? gridSize * 2 - minY : 0;

  const existingPositions = options?.existingPositions;
  const preserveExisting =
    Boolean(existingPositions) && options?.forceRelayout !== true;

  // If preserving existing positions, translate dagre coords into the existing coordinate frame.
  let translateX = 0;
  let translateY = 0;
  if (preserveExisting && existingPositions) {
    for (const step of strategy.steps) {
      const existing = existingPositions.get(step.id);
      const dagre = dagrePositions.get(step.id);
      if (existing && dagre) {
        const dagreX = snap(dagre.x + offsetX);
        const dagreY = snap(dagre.y + offsetY);
        translateX = existing.x - dagreX;
        translateY = existing.y - dagreY;
        break;
      }
    }
  }

  for (const step of strategy.steps) {
    const kind = inferStepKind(step);
    const existing = preserveExisting ? existingPositions?.get(step.id) : undefined;
    const dagrePos = dagrePositions.get(step.id);
    const finalPos =
      existing ||
      (dagrePos
        ? {
            x: snap(dagrePos.x + offsetX + translateX),
            y: snap(dagrePos.y + offsetY + translateY),
          }
        : undefined);
    if (!finalPos) continue;
    nodes.push({
      id: step.id,
      type: "step",
      position: {
        x: finalPos.x,
        y: finalPos.y,
      },
      data: {
        step,
        onOperatorChange,
        onAddToChat,
        onOpenDetails,
        isUnsaved: unsavedStepIds?.has(step.id) ?? false,
        // UI connection affordances:
        // - only show root outputs when the graph has multiple roots (i.e. output is "missing")
        showOutputHandle: shouldShowRootOutputs && rootSet.has(step.id),
        // - only show input slots when they are missing
        showPrimaryInputHandle:
          (kind === "transform" || kind === "combine") && !step.primaryInputStepId,
        showSecondaryInputHandle: kind === "combine" && !step.secondaryInputStepId,
      },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    });

    if (step.primaryInputStepId) {
      // Guard: avoid edges to missing nodes (e.g. after a node delete).
      if (!stepMap.has(step.primaryInputStepId)) continue;
      edges.push({
        id: `${step.primaryInputStepId}-${step.id}-primary`,
        source: step.primaryInputStepId,
        target: step.id,
        sourceHandle: "right",
        targetHandle: "left",
        type: "step",
        label: step.secondaryInputStepId ? "L" : undefined,
        labelStyle: step.secondaryInputStepId
          ? { fontSize: 11, fontWeight: 700, fill: "#0f172a" }
          : undefined,
        labelBgStyle: step.secondaryInputStepId
          ? { fill: "#ffffff", stroke: "#cbd5e1", strokeWidth: 1 }
          : undefined,
        labelBgPadding: step.secondaryInputStepId ? [6, 2] : undefined,
        labelBgBorderRadius: step.secondaryInputStepId ? 6 : undefined,
        style: { stroke: "#94a3b8", strokeWidth: 2 },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: "#94a3b8",
          width: 14,
          height: 14,
        },
      });
    }

    if (step.secondaryInputStepId) {
      if (!stepMap.has(step.secondaryInputStepId)) continue;
      edges.push({
        id: `${step.secondaryInputStepId}-${step.id}-secondary`,
        source: step.secondaryInputStepId,
        target: step.id,
        sourceHandle: "right",
        targetHandle: "left-secondary",
        type: "step",
        label: "R",
        labelStyle: { fontSize: 11, fontWeight: 700, fill: "#0f172a" },
        labelBgStyle: { fill: "#ffffff", stroke: "#cbd5e1", strokeWidth: 1 },
        labelBgPadding: [6, 2],
        labelBgBorderRadius: 6,
        style: { stroke: "#64748b", strokeWidth: 2 },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: "#64748b",
          width: 14,
          height: 14,
        },
      });
    }
  }

  return { nodes, edges };
}

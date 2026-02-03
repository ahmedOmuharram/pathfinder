import dagre from "dagre";
import type { Edge, Node } from "reactflow";
import { MarkerType, Position } from "reactflow";
import type { Step, Strategy } from "./types";

export function deserializeStrategyToGraph(
  strategy: Strategy | null,
  onOperatorChange?: (stepId: string, operator: string) => void,
  onAddToChat?: (stepId: string) => void,
  onOpenDetails?: (stepId: string) => void,
  unsavedStepIds?: Set<string>
): { nodes: Node[]; edges: Edge[] } {
  if (!strategy || strategy.steps.length === 0) {
    return { nodes: [], edges: [] };
  }

  const nodes: Node[] = [];
  const edges: Edge[] = [];
  const stepMap = new Map<string, Step>();

  for (const step of strategy.steps) {
    stepMap.set(step.id, step);
  }

  const gridSize = 28;
  const nodeWidth = 224;
  const nodeHeight = 112;
  const snap = (value: number) => Math.round(value / gridSize) * gridSize;

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
    if (step.primaryInputStepId) {
      layoutGraph.setEdge(step.primaryInputStepId, step.id);
    }
    if (step.secondaryInputStepId) {
      layoutGraph.setEdge(step.secondaryInputStepId, step.id);
    }
  }

  dagre.layout(layoutGraph);

  const positions = new Map<string, { x: number; y: number }>();
  layoutGraph.nodes().forEach((id: string) => {
    const node = layoutGraph.node(id) as { x: number; y: number; width: number; height: number };
    positions.set(id, {
      x: node.x - node.width / 2,
      y: node.y - node.height / 2,
    });
  });

  const allPositions = Array.from(positions.values());
  const minX = Math.min(...allPositions.map((pos) => pos.x));
  const minY = Math.min(...allPositions.map((pos) => pos.y));
  const offsetX = minX < gridSize * 2 ? gridSize * 2 - minX : 0;
  const offsetY = minY < gridSize * 2 ? gridSize * 2 - minY : 0;

  for (const step of strategy.steps) {
    const position = positions.get(step.id);
    if (!position) continue;
    nodes.push({
      id: step.id,
      type: "step",
      position: {
        x: snap(position.x + offsetX),
        y: snap(position.y + offsetY),
      },
      data: {
        step,
        onOperatorChange,
        onAddToChat,
        onOpenDetails,
        isUnsaved: unsavedStepIds?.has(step.id) ?? false,
      },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    });

    if (step.primaryInputStepId) {
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

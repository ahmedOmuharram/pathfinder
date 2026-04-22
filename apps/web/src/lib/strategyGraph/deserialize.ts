import type { Edge, Node } from "@xyflow/react";
import { MarkerType, Position } from "@xyflow/react";
import type { Step, Strategy } from "@pathfinder/shared";
import { inferStepKind } from "./kind";
import type { StepPositions } from "./layout";

type ExistingPositions = Map<string, { x: number; y: number }>;
type DeserializeOptions = {
  /**
   * Fresh layout positions (ELK). Used for nodes without an existing position
   * and — when `forceRelayout` is set — for every node.
   */
  computedPositions?: StepPositions;
  /**
   * User-moved positions preserved across re-renders. Takes precedence over
   * `computedPositions` unless `forceRelayout` is true.
   */
  existingPositions?: ExistingPositions;
  /** Ignore existing positions and relayout from `computedPositions`. */
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
    if (step.primaryInputStepId != null) {
      usedAsInputCount.set(
        step.primaryInputStepId,
        (usedAsInputCount.get(step.primaryInputStepId) ?? 0) + 1,
      );
    }
    if (step.secondaryInputStepId != null) {
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
  const snap = (value: number) => Math.round(value / gridSize) * gridSize;

  const computed: StepPositions =
    options?.computedPositions ?? new Map<string, { x: number; y: number }>();
  const existing: ExistingPositions | undefined =
    options?.forceRelayout === true ? undefined : options?.existingPositions;

  // Normalize computed positions so minX/minY respect the gridSize margin.
  const allComputed = Array.from(computed.values());
  let offsetX = 0;
  let offsetY = 0;
  if (allComputed.length > 0) {
    const minX = Math.min(...allComputed.map((p) => p.x));
    const minY = Math.min(...allComputed.map((p) => p.y));
    offsetX = minX < gridSize * 2 ? gridSize * 2 - minX : 0;
    offsetY = minY < gridSize * 2 ? gridSize * 2 - minY : 0;
  }

  // When preserving, anchor the computed frame onto the existing frame using
  // the first node that appears in both.
  let translateX = 0;
  let translateY = 0;
  if (existing) {
    for (const step of strategy.steps) {
      const ex = existing.get(step.id);
      const cp = computed.get(step.id);
      if (ex && cp) {
        translateX = ex.x - snap(cp.x + offsetX);
        translateY = ex.y - snap(cp.y + offsetY);
        break;
      }
    }
  }

  for (const [stepIndex, step] of strategy.steps.entries()) {
    const kind = inferStepKind(step);
    const ex = existing ? existing.get(step.id) : null;
    const cp = computed.get(step.id);
    const finalPos =
      ex ??
      (cp
        ? {
            x: snap(cp.x + offsetX + translateX),
            y: snap(cp.y + offsetY + translateY),
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
        showOutputHandle: shouldShowRootOutputs && rootSet.has(step.id),
        showPrimaryInputHandle:
          (kind === "transform" || kind === "combine") &&
          step.primaryInputStepId == null,
        showSecondaryInputHandle:
          kind === "combine" && step.secondaryInputStepId == null,
        enterDelayIndex: stepIndex,
      },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    });

    if (step.primaryInputStepId != null) {
      if (!stepMap.has(step.primaryInputStepId)) continue;
      const hasSecondary = step.secondaryInputStepId != null;
      const primaryEdge: Edge = {
        id: `${step.primaryInputStepId}-${step.id}-primary`,
        source: step.primaryInputStepId,
        target: step.id,
        sourceHandle: "right",
        targetHandle: "left",
        type: "step",
        style: { stroke: "#94a3b8", strokeWidth: 2 },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: "#94a3b8",
          width: 14,
          height: 14,
        },
      };
      if (hasSecondary) {
        primaryEdge.label = "L (primary)";
        primaryEdge.labelStyle = { fontSize: 11, fontWeight: 700, fill: "#0f172a" };
        primaryEdge.labelBgStyle = {
          fill: "#ffffff",
          stroke: "#cbd5e1",
          strokeWidth: 1,
        };
        primaryEdge.labelBgPadding = [6, 2];
        primaryEdge.labelBgBorderRadius = 6;
      }
      edges.push(primaryEdge);
    }

    if (step.secondaryInputStepId != null) {
      if (!stepMap.has(step.secondaryInputStepId)) continue;
      edges.push({
        id: `${step.secondaryInputStepId}-${step.id}-secondary`,
        source: step.secondaryInputStepId,
        target: step.id,
        sourceHandle: "right",
        targetHandle: "left-secondary",
        type: "step",
        label: "R (secondary)",
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

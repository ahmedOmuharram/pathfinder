/**
 * Lightweight SVG-based minimap of a strategy graph.
 *
 * Renders colored rectangles for each step and lines for edges,
 * using dagre for layout — no ReactFlow or heavy hooks involved.
 */
import { useMemo } from "react";
import dagre from "dagre";
import type { StrategyWithMeta } from "@/types/strategy";
import { inferStepKind } from "@/core/strategyGraph";

const NODE_W = 80;
const NODE_H = 28;
const PADDING = 12;

const KIND_COLORS: Record<string, { fill: string; stroke: string }> = {
  search: { fill: "#d1fae5", stroke: "#6ee7b7" },
  combine: { fill: "#e0f2fe", stroke: "#7dd3fc" },
  transform: { fill: "#ede9fe", stroke: "#c4b5fd" },
  default: { fill: "#f1f5f9", stroke: "#cbd5e1" },
};

export function StrategyMinimap(props: { strategy: StrategyWithMeta | null }) {
  const { strategy } = props;
  const steps = useMemo(() => strategy?.steps ?? [], [strategy?.steps]);

  const layout = useMemo(() => {
    if (steps.length === 0) return null;

    const g = new dagre.graphlib.Graph();
    g.setGraph({ rankdir: "LR", nodesep: 16, ranksep: 32 });
    g.setDefaultEdgeLabel(() => ({}));

    for (const step of steps) {
      g.setNode(step.id, { width: NODE_W, height: NODE_H });
    }
    for (const step of steps) {
      if (step.primaryInputStepId) {
        g.setEdge(step.primaryInputStepId, step.id);
      }
      if (step.secondaryInputStepId) {
        g.setEdge(step.secondaryInputStepId, step.id);
      }
    }

    dagre.layout(g);

    const nodes = steps.map((step) => {
      const pos = g.node(step.id);
      const kind = inferStepKind(step);
      const colors = KIND_COLORS[kind] ?? KIND_COLORS.default;
      return {
        id: step.id,
        x: pos.x - NODE_W / 2,
        y: pos.y - NODE_H / 2,
        kind,
        colors,
        label: step.displayName ?? step.searchName ?? step.id,
      };
    });

    const edges: { x1: number; y1: number; x2: number; y2: number }[] = [];
    for (const step of steps) {
      const target = g.node(step.id);
      if (step.primaryInputStepId && g.node(step.primaryInputStepId)) {
        const source = g.node(step.primaryInputStepId);
        edges.push({
          x1: source.x + NODE_W / 2,
          y1: source.y,
          x2: target.x - NODE_W / 2,
          y2: target.y,
        });
      }
      if (step.secondaryInputStepId && g.node(step.secondaryInputStepId)) {
        const source = g.node(step.secondaryInputStepId);
        edges.push({
          x1: source.x + NODE_W / 2,
          y1: source.y,
          x2: target.x - NODE_W / 2,
          y2: target.y,
        });
      }
    }

    // Compute bounding box
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    for (const n of nodes) {
      minX = Math.min(minX, n.x);
      minY = Math.min(minY, n.y);
      maxX = Math.max(maxX, n.x + NODE_W);
      maxY = Math.max(maxY, n.y + NODE_H);
    }

    const width = maxX - minX + PADDING * 2;
    const height = maxY - minY + PADDING * 2;
    const offsetX = -minX + PADDING;
    const offsetY = -minY + PADDING;

    return { nodes, edges, width, height, offsetX, offsetY };
  }, [steps]);

  if (!layout || steps.length === 0) {
    return (
      <div className="flex h-full w-full items-center justify-center text-[10px] text-slate-400">
        No steps
      </div>
    );
  }

  return (
    <svg
      viewBox={`0 0 ${layout.width} ${layout.height}`}
      className="h-full w-full"
      preserveAspectRatio="xMidYMid meet"
      aria-label="Strategy graph preview"
    >
      {layout.edges.map((edge, i) => (
        <line
          key={i}
          x1={edge.x1 + layout.offsetX}
          y1={edge.y1 + layout.offsetY}
          x2={edge.x2 + layout.offsetX}
          y2={edge.y2 + layout.offsetY}
          stroke="#cbd5e1"
          strokeWidth={1.5}
        />
      ))}
      {layout.nodes.map((node) => (
        <g
          key={node.id}
          transform={`translate(${node.x + layout.offsetX}, ${node.y + layout.offsetY})`}
        >
          <rect
            width={NODE_W}
            height={NODE_H}
            rx={6}
            fill={node.colors.fill}
            stroke={node.colors.stroke}
            strokeWidth={1.5}
          />
          <text
            x={NODE_W / 2}
            y={NODE_H / 2}
            textAnchor="middle"
            dominantBaseline="central"
            className="fill-slate-700"
            fontSize={8}
          >
            {node.label.length > 12 ? `${node.label.slice(0, 11)}…` : node.label}
          </text>
        </g>
      ))}
    </svg>
  );
}

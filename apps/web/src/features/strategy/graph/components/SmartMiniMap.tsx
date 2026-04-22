"use client";

import { motion } from "motion/react";
import { MiniMap } from "@xyflow/react";
import type { StepKind } from "@pathfinder/shared";
import { useCanvasIdle } from "@/features/strategy/graph/hooks/useCanvasIdle";

const MINIMAP_NODE_COLOR: Record<StepKind, string> = {
  search: "#10b981",
  combine: "#0ea5e9",
  transform: "#8b5cf6",
};

function minimapNodeColor(node: { data?: { step?: { kind?: string } } }): string {
  const kind = node.data?.step?.kind;
  if (kind === "search" || kind === "combine" || kind === "transform") {
    return MINIMAP_NODE_COLOR[kind];
  }
  return "#94a3b8";
}

interface SmartMiniMapProps {
  /** Total node count. The minimap is hidden when this is ≤ 8. */
  nodeCount: number;
  /** Idle threshold in ms. Defaults to 3000. */
  idleMs?: number;
}

export function SmartMiniMap({ nodeCount, idleMs = 3000 }: SmartMiniMapProps) {
  const idle = useCanvasIdle({ idleMs });
  if (nodeCount <= 8) return null;

  return (
    <motion.div
      data-testid="smart-mini-map"
      animate={{ opacity: idle ? 0.2 : 1 }}
      transition={{ duration: 0.2 }}
      whileHover={{ opacity: 1 }}
    >
      <MiniMap
        nodeColor={minimapNodeColor}
        maskColor="rgba(0,0,0,0.1)"
        className="rounded-lg border border-border bg-card"
      />
    </motion.div>
  );
}

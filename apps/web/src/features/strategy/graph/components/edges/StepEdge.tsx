"use client";

import { motion } from "motion/react";
import { type EdgeProps, getSmoothStepPath } from "@xyflow/react";
import { usePrefersReducedMotion } from "@/lib/hooks/usePrefersReducedMotion";
import { EDGE_DRAW_DURATION_MS } from "@/lib/motion/presets";

const STROKE_WIDTH = 1.5;
const STROKE_COLOR = "currentColor";

export function StepEdge(props: EdgeProps) {
  const {
    id,
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    markerEnd,
  } = props;

  const reduced = usePrefersReducedMotion();
  const [path, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
  });

  return (
    <motion.path
      id={id}
      d={path}
      data-testid={`step-edge-${id}`}
      data-label-x={labelX}
      data-label-y={labelY}
      fill="none"
      stroke={STROKE_COLOR}
      strokeWidth={STROKE_WIDTH}
      markerEnd={markerEnd}
      className="text-muted-foreground"
      initial={reduced ? { pathLength: 1 } : { pathLength: 0 }}
      animate={{ pathLength: 1 }}
      exit={reduced ? { pathLength: 1 } : { pathLength: 0 }}
      transition={{
        duration: reduced ? 0 : EDGE_DRAW_DURATION_MS / 1000,
        ease: "easeOut",
      }}
    />
  );
}

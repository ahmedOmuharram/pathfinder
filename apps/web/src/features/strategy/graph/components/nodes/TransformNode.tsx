"use client";

import { Handle, Position } from "@xyflow/react";
import { useStepSnapshot } from "@/state/strategy/useStepSnapshot";
import { NodeShell } from "./NodeShell";
import type { StepNodeProps } from "./types";

export const TRANSFORM_NODE_WIDTH = 184;
export const TRANSFORM_NODE_HEIGHT = 64;

const CHEVRON_CLIP =
  "polygon(0% 0%, calc(100% - 14px) 0%, 100% 50%, calc(100% - 14px) 100%, 0% 100%)";

export function TransformNode(props: StepNodeProps) {
  const {
    step,
    selected,
    isUnsaved = false,
    showOutputHandle = false,
    showPrimaryInputHandle = false,
    enterDelayIndex,
    onAddToChat,
    onOpenDetails,
    onRename,
    onDuplicate,
    onDelete,
  } = props;
  const snapshot = useStepSnapshot(step);

  return (
    <NodeShell
      kind="transform"
      step={step}
      selected={selected}
      isUnsaved={isUnsaved}
      width={TRANSFORM_NODE_WIDTH}
      height={TRANSFORM_NODE_HEIGHT}
      snapshot={snapshot}
      enterDelayIndex={enterDelayIndex}
      onAddToChat={onAddToChat}
      onOpenDetails={onOpenDetails}
      onRename={onRename}
      onDuplicate={onDuplicate}
      onDelete={onDelete}
      surfaceClipPath={CHEVRON_CLIP}
      surfaceClipDataAttr="chevron-right"
      handles={
        <>
          <Handle
            type="target"
            position={Position.Left}
            id="left"
            data-testid={`rf-handle-${step.id}-primary`}
            isConnectable={showPrimaryInputHandle}
            style={{ top: "50%" }}
            className={`z-10 h-3 w-3 border-2 border-white ${
              showPrimaryInputHandle
                ? "bg-foreground"
                : "pointer-events-none bg-foreground opacity-0"
            }`}
          />
          <Handle
            type="source"
            position={Position.Right}
            id="right"
            data-testid={`rf-handle-${step.id}-output`}
            isConnectable={showOutputHandle}
            style={{ top: "50%" }}
            className={`z-10 h-3 w-3 border-2 border-input ${
              showOutputHandle
                ? "bg-card"
                : "pointer-events-none bg-card opacity-0"
            }`}
          />
        </>
      }
    />
  );
}

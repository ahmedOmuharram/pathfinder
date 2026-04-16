"use client";

import { Handle, Position } from "@xyflow/react";
import type { Node, NodeProps } from "@xyflow/react";
import type { CheckpointNode } from "@pathfinder/shared/generated/types/CheckpointNode";
import { match } from "ts-pattern";

import { ForkButton } from "./ForkButton";

function sourceIcon(source: string): string {
  return match(source)
    .with("input", () => "⬇")
    .with("loop", () => "·")
    .with("update", () => "⭑")
    .with("fork", () => "⎇")
    .otherwise(() => "·");
}

export function BranchNode({
  data,
  selected,
}: NodeProps<Node<CheckpointNode>>) {
  return (
    <div
      data-branch-node
      className={`rounded-md border-2 bg-card px-3 py-2 text-xs shadow-sm transition ${
        selected === true ? "border-primary" : "border-border"
      }`}
      style={{ width: 220 }}
    >
      <Handle type="target" position={Position.Top} />
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-muted-foreground">
          {sourceIcon(data.source)}
        </span>
        <span className="font-semibold">{data.node ?? "—"}</span>
        <span className="text-muted-foreground">step {data.step}</span>
      </div>
      {data.label != null && data.label !== "" ? (
        <div className="mt-1 truncate text-primary">{data.label}</div>
      ) : null}
      {selected === true ? (
        <div className="mt-1.5 flex justify-end">
          <ForkButton
            chatId={data.threadId}
            checkpointId={data.checkpointId}
          />
        </div>
      ) : null}
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}

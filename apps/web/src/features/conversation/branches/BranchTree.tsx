"use client";

import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  ReactFlowProvider,
} from "@xyflow/react";
import type { Node } from "@xyflow/react";
import { useQuery } from "@tanstack/react-query";
import { parseAsString, useQueryState } from "nuqs";
import type { CheckpointNode } from "@pathfinder/shared/generated/types/CheckpointNode";
import { client } from "@/lib/api/client";
import { layoutCheckpointTree } from "./layoutCheckpointTree";
import { BranchNode } from "./BranchNode";
import "@xyflow/react/dist/style.css";

const NODE_TYPES = { checkpointNode: BranchNode };

function findDefaultLeaf(checkpoints: CheckpointNode[]): string | null {
  if (checkpoints.length === 0) return null;
  const childSet = new Set(
    checkpoints
      .map((c) => c.parentCheckpointId)
      .filter((id): id is string => id !== null),
  );
  const leaves = checkpoints.filter((c) => !childSet.has(c.checkpointId));
  if (leaves.length === 0) return null;
  let best = leaves[0]!;
  for (const leaf of leaves) {
    if (leaf.step > best.step) best = leaf;
  }
  return best.checkpointId;
}

function BranchTreeInner({ chatId }: { chatId: string }) {
  const { data: checkpoints = [] } = useQuery({
    queryKey: ["checkpoints", chatId],
    queryFn: async () => {
      const resp = await client<CheckpointNode[]>({
        method: "get",
        url: `/api/v1/conversations/${chatId}/checkpoints`,
      });
      return resp.data;
    },
    enabled: chatId !== "",
  });

  const layoutKey = checkpoints
    .map((c: CheckpointNode) => c.checkpointId)
    .join(",");
  const layout = useQuery({
    queryKey: ["checkpoints-layout", chatId, layoutKey],
    queryFn: () => layoutCheckpointTree(checkpoints),
    enabled: checkpoints.length > 0,
  });

  const [activeBranch, setActiveBranch] = useQueryState(
    "branch",
    parseAsString,
  );

  const resolvedActive = activeBranch ?? findDefaultLeaf(checkpoints);

  const nodes: Node[] = (layout.data?.nodes ?? []).map((n) => ({
    ...n,
    selected: n.id === resolvedActive,
  }));

  return (
    <div className="h-full w-full" data-testid="branch-tree">
      <ReactFlow
        nodes={nodes}
        edges={layout.data?.edges ?? []}
        nodeTypes={NODE_TYPES}
        fitView
        onNodeClick={(_e, node) => {
          void setActiveBranch(node.id);
        }}
        proOptions={{ hideAttribution: true }}
      >
        <Background />
        <MiniMap />
        <Controls />
      </ReactFlow>
    </div>
  );
}

export function BranchTree({ chatId }: { chatId: string }) {
  return (
    <ReactFlowProvider>
      <BranchTreeInner chatId={chatId} />
    </ReactFlowProvider>
  );
}

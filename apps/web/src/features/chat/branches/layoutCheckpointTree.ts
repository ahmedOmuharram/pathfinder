import ELK from "elkjs/lib/elk.bundled.js";
import type { Node, Edge } from "@xyflow/react";
import type { CheckpointNode } from "@pathfinder/shared/generated/types/CheckpointNode";

const elk = new ELK();

const NODE_WIDTH = 220;
const NODE_HEIGHT = 60;

export async function layoutCheckpointTree(
  checkpoints: CheckpointNode[],
): Promise<{ nodes: Node[]; edges: Edge[] }> {
  if (checkpoints.length === 0) return { nodes: [], edges: [] };

  const elkGraph = {
    id: "root",
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": "DOWN",
      "elk.layered.nodePlacement.strategy": "NETWORK_SIMPLEX",
      "elk.spacing.nodeNode": "40",
      "elk.layered.spacing.nodeNodeBetweenLayers": "80",
    },
    children: checkpoints.map((c) => ({
      id: c.checkpointId,
      width: NODE_WIDTH,
      height: NODE_HEIGHT,
    })),
    edges: checkpoints
      .filter((c): c is CheckpointNode & { parentCheckpointId: string } => c.parentCheckpointId !== null)
      .map((c) => ({
        id: `${c.parentCheckpointId}->${c.checkpointId}`,
        sources: [c.parentCheckpointId],
        targets: [c.checkpointId],
      })),
  };

  const laidOut = await elk.layout(elkGraph);
  const byId = new Map(checkpoints.map((c) => [c.checkpointId, c]));

  const nodes: Node[] = (laidOut.children ?? []).map((child) => ({
    id: child.id,
    type: "checkpointNode",
    position: { x: child.x ?? 0, y: child.y ?? 0 },
    data: byId.get(child.id)!,
  }));

  const edges: Edge[] = [];
  for (const e of laidOut.edges) {
    const source = e.sources[0];
    const target = e.targets[0];
    if (source === undefined || target === undefined) continue;
    edges.push({ id: e.id, source, target, type: "default" });
  }

  return { nodes, edges };
}

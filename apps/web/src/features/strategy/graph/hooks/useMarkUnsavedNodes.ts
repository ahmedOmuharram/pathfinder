import { useEffect } from "react";
import type { Node } from "reactflow";
import type { StrategyStep } from "@/features/strategy/types";
import { isRecord } from "@/lib/utils/isRecord";

type NodeData = Record<string, unknown> & {
  isUnsaved?: boolean;
  step?: StrategyStep;
  message?: string;
};

export function useMarkUnsavedNodes(args: {
  dirtyStepIds: Set<string>;
  dirtyKey: string;
  setNodes: (updater: (prev: Node[]) => Node[]) => void;
}) {
  const { dirtyStepIds, dirtyKey, setNodes } = args;

  useEffect(() => {
    setNodes((prev) =>
      prev.map((node) => ({
        ...node,
        data: {
          ...((node.data && isRecord(node.data)
            ? (node.data as NodeData)
            : {}) as NodeData),
          isUnsaved: dirtyStepIds.has(node.id),
        },
      })),
    );
  }, [dirtyKey, dirtyStepIds, setNodes]);
}

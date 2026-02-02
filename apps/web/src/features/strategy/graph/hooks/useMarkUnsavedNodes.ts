import { useEffect } from "react";
import type { Node } from "reactflow";

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
          ...(node.data as any),
          isUnsaved: dirtyStepIds.has(node.id),
        },
      }))
    );
  }, [dirtyKey, dirtyStepIds, setNodes]);
}


import { useMemo } from "react";
import type { Node } from "reactflow";
import type { CombineMismatchGroup } from "@/core/strategyGraph";

export function useWarningGroupNodes(args: {
  nodes: Node[];
  groups: CombineMismatchGroup[];
  defaultNodeWidth?: number;
  defaultNodeHeight?: number;
  padding?: number;
}): Node[] {
  const {
    nodes,
    groups,
    defaultNodeWidth = 224,
    defaultNodeHeight = 112,
    padding = 16,
  } = args;

  return useMemo(() => {
    if (groups.length === 0) return [];
    return groups.flatMap((group) => {
      const targetNodes = nodes.filter((node) => group.ids.has(node.id));
      if (targetNodes.length < 2) return [];
      const minX = Math.min(...targetNodes.map((node) => node.position.x));
      const minY = Math.min(...targetNodes.map((node) => node.position.y));
      const maxX = Math.max(
        ...targetNodes.map(
          (node) => node.position.x + (node.width ?? defaultNodeWidth),
        ),
      );
      const maxY = Math.max(
        ...targetNodes.map(
          (node) => node.position.y + (node.height ?? defaultNodeHeight),
        ),
      );
      const groupWidth = maxX - minX + padding * 2;
      const groupHeight = maxY - minY + padding * 2;
      const groupLeft = minX - padding;
      const groupTop = minY - padding;
      return [
        {
          id: `warning-group-${group.id}`,
          type: "warningGroup",
          position: { x: groupLeft, y: groupTop },
          data: { message: group.message },
          className: "warning-group-node warning-dash",
          selectable: false,
          draggable: false,
          connectable: false,
          deletable: false,
          focusable: false,
          width: groupWidth,
          height: groupHeight,
          style: {
            width: groupWidth,
            height: groupHeight,
            zIndex: 50,
            pointerEvents: "none",
            background: "transparent",
            overflow: "visible",
            borderRadius: 14,
            boxSizing: "border-box",
          },
        } as Node,
        {
          id: `warning-icon-${group.id}`,
          type: "warningIcon",
          position: { x: groupLeft - 8, y: groupTop - 8 },
          data: { message: group.message },
          selectable: false,
          draggable: false,
          connectable: false,
          deletable: false,
          focusable: false,
          width: 24,
          height: 24,
          style: {
            width: 24,
            height: 24,
            zIndex: 60,
            pointerEvents: "auto",
            background: "transparent",
          },
        } as Node,
      ];
    });
  }, [groups, nodes, defaultNodeWidth, defaultNodeHeight, padding]);
}

import { useCallback, useEffect, useRef } from "react";

export function useAutoFitView(args: {
  enabled: boolean;
  nodeCount: number;
  userHasMoved: boolean;
  fitView: () => void;
}) {
  const { enabled, nodeCount, userHasMoved, fitView } = args;
  const prevNodeCountRef = useRef(0);

  useEffect(() => {
    if (!enabled) return;
    const prev = prevNodeCountRef.current;
    if (nodeCount > prev && !userHasMoved) {
      requestAnimationFrame(() => fitView());
    }
    prevNodeCountRef.current = nodeCount;
  }, [enabled, nodeCount, userHasMoved, fitView]);

  const reset = useCallback(() => {
    prevNodeCountRef.current = 0;
  }, []);

  return {
    reset,
  };
}

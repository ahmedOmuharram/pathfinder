import { useCallback, useEffect, useRef, useState } from "react";
import { usePrevious } from "@/shared/hooks/usePrevious";

export function useAutoFitView(args: {
  enabled: boolean;
  nodeCount: number;
  userHasMoved: boolean;
  fitView: () => void;
}) {
  const { enabled, nodeCount, userHasMoved, fitView } = args;
  const prevNodeCount = usePrevious(nodeCount);
  const hasResetRef = useRef(false);
  const [resetTrigger, setResetTrigger] = useState(0);

  useEffect(() => {
    if (!enabled) return;
    const prev = hasResetRef.current ? 0 : (prevNodeCount ?? 0);
    if (hasResetRef.current) hasResetRef.current = false;
    if (nodeCount > prev && !userHasMoved) {
      requestAnimationFrame(() => fitView());
    }
  }, [enabled, nodeCount, prevNodeCount, userHasMoved, fitView, resetTrigger]);

  const reset = useCallback(() => {
    hasResetRef.current = true;
    setResetTrigger((t) => t + 1);
  }, []);

  return {
    reset,
  };
}

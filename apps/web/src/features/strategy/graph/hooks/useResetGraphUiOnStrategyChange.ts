import { useEffect } from "react";
import type { MutableRef } from "@/shared/types/refs";

export function useResetGraphUiOnStrategyChange(args: {
  strategyId: string | undefined;
  setUserHasMoved: (value: boolean) => void;
  autoFitReset: () => void;
  setSelectedNodeIds: (value: string[]) => void;
  selectedNodeIdsRef: MutableRef<string[]>;
}) {
  const {
    strategyId,
    setUserHasMoved,
    autoFitReset,
    setSelectedNodeIds,
    selectedNodeIdsRef,
  } = args;

  useEffect(() => {
    setUserHasMoved(false);
    autoFitReset();
    setSelectedNodeIds([]);
    selectedNodeIdsRef.current = [];
  }, [
    strategyId,
    autoFitReset,
    selectedNodeIdsRef,
    setSelectedNodeIds,
    setUserHasMoved,
  ]);
}

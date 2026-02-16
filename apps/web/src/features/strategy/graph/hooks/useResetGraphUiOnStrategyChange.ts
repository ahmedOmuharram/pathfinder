import { useEffect } from "react";
import { usePrevious } from "@/shared/hooks/usePrevious";

export function useResetGraphUiOnStrategyChange(args: {
  strategyId: string | undefined;
  setUserHasMoved: (value: boolean) => void;
  autoFitReset: () => void;
  setSelectedNodeIds: (value: string[]) => void;
}) {
  const { strategyId, setUserHasMoved, autoFitReset, setSelectedNodeIds } = args;

  const prevStrategyId = usePrevious(strategyId);

  useEffect(() => {
    if (prevStrategyId === undefined) return;
    if (prevStrategyId === strategyId) return;
    setUserHasMoved(false);
    autoFitReset();
    setSelectedNodeIds([]);
  }, [strategyId, prevStrategyId, autoFitReset, setSelectedNodeIds, setUserHasMoved]);
}

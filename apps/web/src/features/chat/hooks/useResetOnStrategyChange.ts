import { useEffect } from "react";
import type { StrategyWithMeta } from "@/types/strategy";
import type { MutableRef } from "@/shared/types/refs";

export function useResetOnStrategyChange(args: {
  strategyId: string | null;
  isStreamingRef: MutableRef<boolean>;
  previousStrategyIdRef: MutableRef<string | null>;
  resetThinking: () => void;
  setIsStreaming: (value: boolean) => void;
  setMessages: (value: any) => void;
  setUndoSnapshots: (value: any) => void;
  pendingUndoSnapshotRef: MutableRef<StrategyWithMeta | null>;
}) {
  const {
    strategyId,
    isStreamingRef,
    previousStrategyIdRef,
    resetThinking,
    setIsStreaming,
    setMessages,
    setUndoSnapshots,
    pendingUndoSnapshotRef,
  } = args;

  useEffect(() => {
    const previousId = previousStrategyIdRef.current;
    previousStrategyIdRef.current = strategyId;

    if (!isStreamingRef.current) {
      resetThinking();
      setIsStreaming(false);
    }

    if (strategyId && previousId && previousId !== strategyId) {
      setMessages([]);
      setUndoSnapshots({});
      pendingUndoSnapshotRef.current = null;
    }

    if (!strategyId) {
      return;
    }
  }, [
    strategyId,
    isStreamingRef,
    previousStrategyIdRef,
    resetThinking,
    setIsStreaming,
    setMessages,
    setUndoSnapshots,
    pendingUndoSnapshotRef,
  ]);
}


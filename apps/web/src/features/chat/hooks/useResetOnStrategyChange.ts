import { useEffect } from "react";
import type { Dispatch, SetStateAction } from "react";
import type { Message } from "@pathfinder/shared";
import type { StrategyWithMeta } from "@/features/strategy/types";
import type { StreamingSession } from "@/features/chat/streaming/StreamingSession";

export function useResetOnStrategyChange(args: {
  strategyId: string | null;
  previousStrategyId: string | null | undefined;
  isStreaming: boolean;
  resetThinking: () => void;
  setIsStreaming: (value: boolean) => void;
  setMessages: Dispatch<SetStateAction<Message[]>>;
  setUndoSnapshots: Dispatch<SetStateAction<Record<number, StrategyWithMeta>>>;
  sessionRef: { current: StreamingSession | null };
}) {
  const {
    strategyId,
    previousStrategyId,
    isStreaming,
    resetThinking,
    setIsStreaming,
    setMessages,
    setUndoSnapshots,
    sessionRef,
  } = args;

  useEffect(() => {
    if (!isStreaming) {
      resetThinking();
      setIsStreaming(false);
    }

    if (strategyId && previousStrategyId && previousStrategyId !== strategyId) {
      setMessages([]);
      setUndoSnapshots({});
      if (sessionRef.current) {
        sessionRef.current.consumeUndoSnapshot();
      }
    }
  }, [
    strategyId,
    previousStrategyId,
    isStreaming,
    resetThinking,
    setIsStreaming,
    setMessages,
    setUndoSnapshots,
    sessionRef,
  ]);
}

import { useEffect } from "react";
import type { Dispatch, SetStateAction } from "react";
import type { Message, StrategyWithMeta } from "@pathfinder/shared";
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
  stopStreaming?: () => void;
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
    stopStreaming,
  } = args;

  useEffect(() => {
    if (!isStreaming) {
      resetThinking();
      setIsStreaming(false);
    }

    if (strategyId && previousStrategyId && previousStrategyId !== strategyId) {
      if (isStreaming && stopStreaming) {
        stopStreaming();
      }
      setIsStreaming(false);
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
    stopStreaming,
  ]);
}

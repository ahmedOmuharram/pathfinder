import { useEffect } from "react";
import type { Dispatch, SetStateAction } from "react";
import type { Message, Strategy } from "@pathfinder/shared";
import type { StreamingSession } from "@/features/chat/streaming/StreamingSession";

export function useResetOnStrategyChange(args: {
  strategyId: string | null;
  previousStrategyId: string | null | undefined;
  resetThinking: () => void;
  setIsStreaming: (value: boolean) => void;
  setMessages: Dispatch<SetStateAction<Message[]>>;
  setUndoSnapshots: Dispatch<SetStateAction<Record<number, Strategy>>>;
  sessionRef: { current: StreamingSession | null };
  stopStreaming?: () => void;
}) {
  const {
    strategyId,
    previousStrategyId,
    resetThinking,
    setIsStreaming,
    setMessages,
    setUndoSnapshots,
    sessionRef,
    stopStreaming,
  } = args;

  useEffect(() => {
    // Only act when the strategy actually changes — not on isStreaming toggles.
    // The !previousStrategyId guard handles the auto-create flow (null → newId)
    // where the stream itself sets strategyId on a new conversation.
    if (!strategyId || !previousStrategyId || previousStrategyId === strategyId) return;

    if (stopStreaming) stopStreaming();
    setIsStreaming(false);
    resetThinking();
    setMessages([]);
    setUndoSnapshots({});
    if (sessionRef.current) {
      sessionRef.current.consumeUndoSnapshot();
    }
  }, [strategyId, previousStrategyId, stopStreaming, setIsStreaming, resetThinking, setMessages, setUndoSnapshots]);
}

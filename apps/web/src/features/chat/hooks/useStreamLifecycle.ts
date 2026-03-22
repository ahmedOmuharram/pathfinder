/**
 * Stream lifecycle management -- state, start/stop, and cleanup.
 *
 * Owns the mutable state that tracks whether a stream is active
 * (loading flag, error, optimization progress) and the subscription
 * / operation-id used to cancel an in-flight operation.
 */

import { useCallback, useState } from "react";
import type { OptimizationProgressData, ToolCall } from "@pathfinder/shared";
import { cancelOperation, type OperationSubscription } from "@/lib/operationSubscribe";
import type { useThinkingState } from "@/features/chat/hooks/useThinkingState";

type Thinking = ReturnType<typeof useThinkingState>;

export function useStreamLifecycle(
  thinking: Thinking,
  onStreamingChange?: (streaming: boolean) => void,
) {
  const [isStreaming, setIsStreamingRaw] = useState(false);

  /** Updates local streaming state and notifies the caller (e.g. global store). */
  const setIsStreaming = useCallback(
    (value: boolean) => {
      setIsStreamingRaw(value);
      onStreamingChange?.(value);
    },
    [onStreamingChange],
  );

  const [apiError, setApiError] = useState<string | null>(null);
  const [optimizationProgress, setOptimizationProgress] =
    useState<OptimizationProgressData | null>(null);
  const [subscription, setSubscription] = useState<OperationSubscription | null>(null);
  const [operationId, setOperationId] = useState<string | null>(null);

  /** Cancel the in-flight operation and reset streaming state. */
  const stopStreaming = useCallback(() => {
    if (operationId != null && operationId !== "") {
      void cancelOperation(operationId);
    }
    subscription?.unsubscribe();
    setSubscription(null);
    setOperationId(null);
    setIsStreaming(false);
  }, [subscription, operationId, setIsStreaming]);

  /** Prepare for a new stream -- reset transient state. */
  const beginStream = useCallback(() => {
    setIsStreaming(true);
    setApiError(null);
    thinking.reset();
    setOptimizationProgress(null);
  }, [thinking, setIsStreaming]);

  /** Called when a stream finishes (success or abort). */
  const finalizeStream = useCallback(
    (toolCalls: ToolCall[]) => {
      setIsStreaming(false);
      setSubscription(null);
      setOperationId(null);
      thinking.finalizeToolCalls(toolCalls.length > 0 ? [...toolCalls] : []);
    },
    [thinking, setIsStreaming],
  );

  /** Called when a stream errors out. Returns true if the error was an abort (suppressed). */
  const handleStreamError = useCallback(
    (
      error: Error,
      toolCalls: ToolCall[],
      onStreamError?: (error: Error) => void,
    ): boolean => {
      setIsStreaming(false);
      setSubscription(null);
      setOperationId(null);
      thinking.finalizeToolCalls(toolCalls.length > 0 ? [...toolCalls] : []);

      const isAbort =
        error.name === "AbortError" ||
        (error.message !== "" && /abort/i.test(error.message));
      if (isAbort) return true;

      console.error("Chat error:", error);
      setApiError(error.message !== "" ? error.message : "Unable to reach the API.");
      onStreamError?.(error);
      return false;
    },
    [thinking, setIsStreaming],
  );

  /** Record subscription + operationId after streamChat resolves. */
  const trackOperation = useCallback((sub: OperationSubscription, opId: string) => {
    setSubscription(sub);
    setOperationId(opId);
  }, []);

  return {
    isStreaming,
    setIsStreaming,
    apiError,
    setApiError,
    optimizationProgress,
    setOptimizationProgress,
    stopStreaming,
    beginStream,
    finalizeStream,
    handleStreamError,
    trackOperation,
  };
}

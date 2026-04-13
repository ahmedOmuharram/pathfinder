/**
 * Stream lifecycle management -- state, start/stop, and cleanup.
 *
 * Owns the mutable state that tracks whether a stream is active
 * (loading flag, error, optimization progress) and the subscription
 * / operation-id used to cancel an in-flight operation.
 */

import { useState } from "react";
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
  const setIsStreaming = (value: boolean) => {
    setIsStreamingRaw(value);
    onStreamingChange?.(value);
  };

  const [apiError, setApiError] = useState<string | null>(null);
  const [optimizationProgress, setOptimizationProgress] =
    useState<OptimizationProgressData | null>(null);
  const [subscription, setSubscription] = useState<OperationSubscription | null>(null);
  const [operationId, setOperationId] = useState<string | null>(null);
  /**
   * Race A guard: if `stopStreaming()` fires during the window between
   * `beginStream()` (flips isStreaming=true) and `trackOperation()` (records
   * the subscription + operationId), we have nothing to cancel yet. Mark the
   * stream as "pending stop" so that when the late `trackOperation()` finally
   * arrives, we cancel the subscription + operation immediately.
   */
  const [pendingStop, setPendingStop] = useState(false);

  /** Cancel the in-flight operation and reset streaming state. */
  const stopStreaming = () => {
    if (operationId != null && operationId !== "") {
      void cancelOperation(operationId);
      subscription?.unsubscribe();
    } else {
      // We are in the beginStream/trackOperation gap -- defer the cancel.
      setPendingStop(true);
    }
    setSubscription(null);
    setOperationId(null);
    setIsStreaming(false);
  };

  /** Prepare for a new stream -- reset transient state. */
  const beginStream = () => {
    setIsStreaming(true);
    setApiError(null);
    setPendingStop(false);
    thinking.reset();
    setOptimizationProgress(null);
  };

  /** Called when a stream finishes (success or abort). */
  const finalizeStream = (toolCalls: ToolCall[]) => {
    setIsStreaming(false);
    setSubscription(null);
    setOperationId(null);
    thinking.finalizeToolCalls(toolCalls.length > 0 ? [...toolCalls] : []);
  };

  /** Called when a stream errors out. Returns true if the error was an abort (suppressed). */
  const handleStreamError = (
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
  };

  /** Record subscription + operationId after streamChat resolves. */
  const trackOperation = (sub: OperationSubscription, opId: string) => {
    if (pendingStop) {
      // Stop was requested during the gap -- cancel immediately.
      void cancelOperation(opId);
      sub.unsubscribe();
      setPendingStop(false);
      return;
    }
    setSubscription(sub);
    setOperationId(opId);
  };

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

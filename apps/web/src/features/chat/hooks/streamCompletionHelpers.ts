/**
 * Pure helpers extracted from useStreamEvents' onComplete callback.
 *
 * Each function handles a single post-stream persistence concern so
 * the hook stays a thin composer.
 */

import type { Message, OptimizationProgressData } from "@pathfinder/shared";

/**
 * Attach accumulated reasoning text to the last assistant message
 * that doesn't already have reasoning.
 *
 * Returns `prev` by reference when no update is needed (no allocation).
 */
export function persistReasoningToLastMessage(
  prev: Message[],
  reasoning: string | null,
): Message[] {
  if (reasoning == null || reasoning === "") return prev;
  for (let i = prev.length - 1; i >= 0; i -= 1) {
    const msg = prev[i];
    if (msg?.role !== "assistant") continue;
    if (msg.reasoning != null) return prev;
    const next = [...prev];
    next[i] = { ...msg, reasoning };
    return next;
  }
  return prev;
}

/**
 * Force-write optimization progress data to the last assistant message.
 *
 * Returns `prev` by reference when no update is needed (no allocation).
 */
export function persistOptimizationDataToLastMessage(
  prev: Message[],
  optimizationProgress: OptimizationProgressData | null,
): Message[] {
  if (!optimizationProgress) return prev;
  for (let i = prev.length - 1; i >= 0; i -= 1) {
    const msg = prev[i];
    if (msg?.role !== "assistant") continue;
    const next = [...prev];
    next[i] = { ...msg, optimizationProgress };
    return next;
  }
  return prev;
}

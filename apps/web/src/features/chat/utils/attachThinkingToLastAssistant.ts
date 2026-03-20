import type { Message, ToolCall } from "@pathfinder/shared";

/**
 * Attach tool-call and sub-kani activity data to the last assistant message.
 *
 * Returns the updated messages array (or the original reference if no change).
 */
export function attachThinkingToLastAssistant(
  messages: Message[],
  calls: ToolCall[],
  activity?: {
    calls: Record<string, ToolCall[]>;
    status: Record<string, string>;
  },
): Message[] {
  if (calls.length === 0 && !activity) return messages;

  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const msg = messages[i];
    if (msg?.role !== "assistant") continue;

    const hasTools = (msg.toolCalls?.length ?? 0) > 0;
    const hasActivity = Object.keys(msg.subKaniActivity?.calls ?? {}).length > 0;
    if (hasTools && hasActivity) return messages;

    const resolvedToolCalls = hasTools || calls.length === 0 ? msg.toolCalls : calls;
    const resolvedActivity =
      hasActivity || activity == null ? msg.subKaniActivity : activity;
    const next = [...messages];
    next[i] = {
      ...msg,
      ...(resolvedToolCalls != null ? { toolCalls: resolvedToolCalls } : {}),
      ...(resolvedActivity != null ? { subKaniActivity: resolvedActivity } : {}),
    };
    return next;
  }
  return messages;
}

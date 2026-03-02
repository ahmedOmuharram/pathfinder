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
    if (messages[i].role !== "assistant") continue;

    const hasTools = (messages[i].toolCalls?.length || 0) > 0;
    const hasActivity =
      Object.keys(messages[i].subKaniActivity?.calls || {}).length > 0;
    if (hasTools && hasActivity) return messages;

    const next = [...messages];
    next[i] = {
      ...messages[i],
      toolCalls: hasTools || calls.length === 0 ? messages[i].toolCalls : calls,
      subKaniActivity:
        hasActivity || !activity ? messages[i].subKaniActivity : activity,
    };
    return next;
  }
  return messages;
}

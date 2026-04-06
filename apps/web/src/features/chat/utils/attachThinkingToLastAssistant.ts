import type { Message, ToolCall } from "@pathfinder/shared";

/**
 * Attach tool-call data to the last assistant message.
 *
 * Returns the updated messages array (or the original reference if no change).
 */
export function attachThinkingToLastAssistant(
  messages: Message[],
  calls: ToolCall[],
): Message[] {
  if (calls.length === 0) return messages;

  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const msg = messages[i];
    if (msg?.role !== "assistant") continue;

    const hasTools = (msg.toolCalls?.length ?? 0) > 0;
    if (hasTools) return messages;

    const next = [...messages];
    next[i] = {
      ...msg,
      toolCalls: calls,
    };
    return next;
  }
  return messages;
}

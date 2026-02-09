import type { Message } from "@pathfinder/shared";

/**
 * Merge fetched messages into current messages.
 * We only accept the fetched list if it is at least as complete as the current list,
 * to avoid overwriting locally-appended streaming state with stale API results.
 */
export function mergeMessages(current: Message[], incoming: Message[]) {
  if (incoming.length === 0) return current;
  if (incoming.length < current.length) return current;

  // If the server response is "long enough" but slightly stale, preserve richer
  // locally-attached fields (e.g. planningArtifacts) for messages that match.
  return incoming.map((msg, idx) => {
    const cur = current[idx];
    if (!cur) return msg;
    if (cur.role !== msg.role) return msg;
    if ((cur.content || "") !== (msg.content || "")) return msg;

    return {
      ...msg,
      toolCalls: msg.toolCalls ?? cur.toolCalls,
      subKaniActivity: msg.subKaniActivity ?? cur.subKaniActivity,
      citations: msg.citations ?? cur.citations,
      planningArtifacts: msg.planningArtifacts ?? cur.planningArtifacts,
    };
  });
}

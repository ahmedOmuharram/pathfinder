import type { Message } from "@pathfinder/shared";

/**
 * Merge fetched messages into current messages.
 * We only accept the fetched list if it is at least as complete as the current list,
 * to avoid overwriting locally-appended streaming state with stale API results.
 */
export function mergeMessages(current: Message[], incoming: Message[]) {
  if (incoming.length === 0) return current;
  if (incoming.length >= current.length) return incoming;
  return current;
}


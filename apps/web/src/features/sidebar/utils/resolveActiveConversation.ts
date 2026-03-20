/**
 * Pure decision logic for resolving which conversation should be active.
 *
 * Extracted from useConversationSidebarData so it can be unit-tested
 * without React hooks.
 */

type ConversationAction =
  | { type: "keep" }
  | { type: "pick"; strategyId: string }
  | { type: "create" }
  | { type: "wait" };

interface ResolveArgs {
  /** Current strategyId (from store / localStorage). */
  strategyId: string | null;
  /** Whether user is authenticated. */
  hasAuth: boolean;
  /** Items currently loaded in the sidebar. */
  strategyItems: { id: string; updatedAt: string }[];
  /** Whether the initial fetch has completed at least once. */
  hasFetched: boolean;
}

/**
 * Determine what action to take for conversation selection.
 *
 * Core invariant: if `strategyId` is already set, NEVER switch away from it.
 * The data-loading layer validates it (404 → clear). This prevents race
 * conditions during rapid refresh where the sidebar list isn't populated yet.
 */
export function resolveActiveConversation({
  strategyId,
  hasAuth,
  strategyItems,
  hasFetched,
}: ResolveArgs): ConversationAction {
  if (!hasAuth) return { type: "wait" };

  // If a conversation is already selected, trust it.
  // useUnifiedChatDataLoading will validate and clear on 404.
  if (strategyId != null) return { type: "keep" };

  // No conversation selected — need to pick one or create.

  if (strategyItems.length === 0) {
    // List hasn't loaded yet — wait for it.
    if (!hasFetched) return { type: "wait" };
    // List loaded but empty — create a new conversation.
    return { type: "create" };
  }

  // Pick the most recently updated conversation.
  const sorted = [...strategyItems].sort(
    (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime(),
  );
  const mostRecent = sorted[0];
  if (mostRecent == null) return { type: "create" };
  return { type: "pick", strategyId: mostRecent.id };
}

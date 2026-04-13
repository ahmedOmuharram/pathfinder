import type { AssistantMessage, Message } from "@pathfinder/shared";

/**
 * Merge fetched messages into current messages.
 *
 * Rules:
 *   - If `incoming` is empty, return `current` unchanged.
 *   - If `incoming` is shorter than `current`, `current` wins entirely
 *     (stale REST snapshot must not erase locally-appended streaming state).
 *   - Otherwise, for each position:
 *     - If the roles differ, the incoming wins (REST is authoritative about
 *       message identity).
 *     - If roles match and this is an assistant message whose content differs
 *       from the current message, treat the CURRENT message as fresher
 *       (it holds in-flight streaming deltas that have not yet been
 *       persisted to the server). Preserve the current content and merge
 *       metadata with a preference for current.
 *     - Otherwise content matches: merge metadata normally.
 *
 * This protects against the "equal-length stale REST overwrites streaming"
 * race (Race D): during streaming, local state has the freshest assistant
 * content; REST snapshots arriving mid-stream may be equal-length but
 * one turn behind.
 */
export function mergeMessages(current: Message[], incoming: Message[]) {
  if (incoming.length === 0) return current;
  if (incoming.length < current.length) return current;

  return incoming.map((msg, idx) => {
    const cur = current[idx];
    if (!cur) return msg;
    if (cur.role !== msg.role) return msg;

    // User messages have no mergeable metadata fields. Prefer the current
    // copy when content matches (preserves any locally-added fields such as
    // entryId), otherwise take the incoming server shape as canonical.
    if (msg.role !== "assistant" || cur.role !== "assistant") {
      return (cur.content || "") === (msg.content || "") ? cur : msg;
    }

    const contentMatches = (cur.content || "") === (msg.content || "");
    // When content differs, the CURRENT (local) copy holds the fresher
    // streaming delta; preserve its content and prefer its metadata.
    // When content matches, use the incoming server shape as the base and
    // fall back to current metadata for any null-out server fields.
    const base: AssistantMessage = contentMatches
      ? msg
      : { ...msg, content: cur.content };

    const pickIncoming = contentMatches;
    // Use explicit null checks (not ??) so that server-returned null doesn't
    // overwrite richer locally-attached data.  ?? only skips undefined, but
    // JSON null deserializes as null which ?? preserves.
    const toolCalls = pickIncoming
      ? (msg.toolCalls ?? cur.toolCalls)
      : (cur.toolCalls ?? msg.toolCalls);
    const citations = pickIncoming
      ? (msg.citations ?? cur.citations)
      : (cur.citations ?? msg.citations);
    const planningArtifacts = pickIncoming
      ? (msg.planningArtifacts ?? cur.planningArtifacts)
      : (cur.planningArtifacts ?? msg.planningArtifacts);
    const problemFrame = pickIncoming
      ? (msg.problemFrame ?? cur.problemFrame)
      : (cur.problemFrame ?? msg.problemFrame);
    const reasoning = pickIncoming
      ? (msg.reasoning ?? cur.reasoning)
      : (cur.reasoning ?? msg.reasoning);
    const optimizationProgress = pickIncoming
      ? (msg.optimizationProgress ?? cur.optimizationProgress)
      : (cur.optimizationProgress ?? msg.optimizationProgress);

    const merged: AssistantMessage = {
      ...base,
      ...(toolCalls != null ? { toolCalls } : {}),
      ...(citations != null ? { citations } : {}),
      ...(planningArtifacts != null ? { planningArtifacts } : {}),
      ...(problemFrame != null ? { problemFrame } : {}),
      ...(reasoning != null ? { reasoning } : {}),
      ...(optimizationProgress != null ? { optimizationProgress } : {}),
    };
    return merged;
  });
}

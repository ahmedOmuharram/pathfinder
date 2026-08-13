import type { TaskCompleted, TaskProgressChunk } from "@pathfinder/shared";

/** The endpoint frames every chunk as `custom` and names it in `kind`. */
export type TaskEventChunk =
  | { type: "custom"; kind: "data-task-progress"; data: TaskProgressChunk }
  | { type: "custom"; kind: "data-task-completed"; data: TaskCompleted }
  | { type: "done"; reason: string };

export interface TaskLiveState {
  latest: TaskProgressChunk | null;
  variants: Map<string, TaskProgressChunk>;
  completed: TaskCompleted | null;
}

function variantId(chunk: TaskProgressChunk): string | null {
  const ts = chunk.toolSpecific;
  if (ts == null || typeof ts !== "object") return null;
  const vid = (ts as Record<string, unknown>)["variantId"];
  return typeof vid === "string" ? vid : null;
}

/**
 * Fold the per-task SSE chunk log into the latest renderable state: the most
 * recent progress chunk, the latest progress per fan-out variant, and the
 * terminal completion if seen. Pure so it can be derived at render time.
 */
export function deriveTaskLiveState(chunks: readonly TaskEventChunk[]): TaskLiveState {
  let latest: TaskProgressChunk | null = null;
  const variants = new Map<string, TaskProgressChunk>();
  let completed: TaskCompleted | null = null;
  for (const chunk of chunks) {
    if (chunk.type !== "custom") continue;
    if (chunk.kind === "data-task-progress") {
      latest = chunk.data;
      const vid = variantId(chunk.data);
      if (vid !== null) variants.set(vid, chunk.data);
    } else {
      completed = chunk.data;
    }
  }
  return { latest, variants, completed };
}

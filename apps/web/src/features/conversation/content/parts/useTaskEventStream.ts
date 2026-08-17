"use client";

import { experimental_streamedQuery, useQuery } from "@tanstack/react-query";

import { streamTypedEvents } from "@/lib/sse/typedEventStream";

import { announceTaskCompletion } from "./taskCompletionResume";
import {
  deriveTaskLiveState,
  type TaskEventChunk,
  type TaskLiveState,
} from "./taskLiveState";

/**
 * Subscribe to a durable task's per-task SSE channel and expose its live
 * state. Progress + completion for durable tasks flow only on
 * `/conversations/{id}/tasks/{taskId}/events` (the worker writes them to
 * `task_progress` + a NOTIFY; the conversation stream excludes task rows), so
 * the started card owns this subscription to keep the progress bar moving.
 *
 * The connection is managed by the streamed query: it opens on mount, closes
 * via the abort signal on unmount, and self-terminates on `[DONE]`. On
 * reconnect (refresh mid-task) the endpoint replays past progress and emits
 * the terminal chunk on connect, so the card catches up.
 *
 * `onComplete` runs on the terminal chunk. The suspended turn streams the rest
 * of its answer only after the task ends, so the caller uses this to re-attach.
 */
export function useTaskEventStream(
  conversationId: string | null,
  taskId: string,
  onComplete: () => void,
): TaskLiveState {
  const { data } = useQuery({
    queryKey: ["conversations", conversationId, "tasks", taskId, "events"] as const,
    queryFn: experimental_streamedQuery({
      streamFn: ({ signal }) =>
        announceTaskCompletion(
          streamTypedEvents<TaskEventChunk>(
            `/api/v1/conversations/${conversationId}/tasks/${taskId}/events`,
            { signal, headers: { "X-Requested-With": "XMLHttpRequest" } },
          ),
          onComplete,
        ),
    }),
    enabled: conversationId !== null && taskId.length > 0,
    staleTime: Infinity,
  });

  return deriveTaskLiveState(data ?? []);
}

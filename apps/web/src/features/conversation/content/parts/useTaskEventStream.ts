"use client";

import { experimental_streamedQuery, useQuery } from "@tanstack/react-query";

import { streamTypedEvents } from "@/lib/sse/typedEventStream";

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
 */
export function useTaskEventStream(
  conversationId: string | null,
  taskId: string,
): TaskLiveState {
  const { data } = useQuery({
    queryKey: ["conversations", conversationId, "tasks", taskId, "events"] as const,
    queryFn: experimental_streamedQuery({
      streamFn: ({ signal }) =>
        streamTypedEvents<TaskEventChunk>(
          `/api/v1/conversations/${conversationId}/tasks/${taskId}/events`,
          { signal, headers: { "X-Requested-With": "XMLHttpRequest" } },
        ),
    }),
    enabled: conversationId !== null && taskId.length > 0,
    staleTime: Infinity,
  });

  return deriveTaskLiveState(data ?? []);
}

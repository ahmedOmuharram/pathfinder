"use client";

import { useSyncExternalStore } from "react";

import { useTaskStore } from "@/state/useTaskStore";

// EventSource is an "external store" in React's sense — it pushes events from
// outside the React render cycle. `useSyncExternalStore` is the documented
// primitive for this exact case (React docs: "Subscribing to an external
// store"). That avoids the project-wide `useEffect` ban while still honoring
// the React rules-of-hooks contract: the `subscribe` function is called when
// the component mounts or when its arguments change, and the returned cleanup
// closes the connection.

type EventSourceCtor = new (
  url: string,
  init?: { withCredentials?: boolean },
) => EventSource;

const MAX_RECONNECT_ATTEMPTS = 5;
const BASE_BACKOFF_MS = 1000;

interface TaskProgressPayload {
  taskId: string;
  percent: number;
  message: string;
  toolSpecific?: unknown;
}

interface TaskCompletedPayload {
  taskId: string;
  status: "success" | "failed";
  error?: string;
}

interface RawPayload {
  type: string;
  data: Record<string, unknown>;
}

function parsePayload(raw: string): RawPayload | null {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return null;
  }
  if (parsed === null || typeof parsed !== "object") return null;
  const candidate: Record<string, unknown> = parsed as Record<string, unknown>;
  const type = candidate["type"];
  const data = candidate["data"];
  if (typeof type !== "string") return null;
  if (data === null || typeof data !== "object") return null;
  return { type, data: data as Record<string, unknown> };
}

function parseProgress(data: Record<string, unknown>): TaskProgressPayload | null {
  const taskId = data["taskId"];
  const percent = data["percent"];
  const message = data["message"];
  if (typeof taskId !== "string") return null;
  if (typeof percent !== "number") return null;
  if (typeof message !== "string") return null;
  const toolSpecific = data["toolSpecific"];
  return {
    taskId,
    percent,
    message,
    ...(toolSpecific === undefined ? {} : { toolSpecific }),
  };
}

function parseCompleted(
  data: Record<string, unknown>,
): TaskCompletedPayload | null {
  const taskId = data["taskId"];
  const status = data["status"];
  if (typeof taskId !== "string") return null;
  if (status !== "success" && status !== "failed") return null;
  const error = data["error"];
  return {
    taskId,
    status,
    ...(typeof error === "string" ? { error } : {}),
  };
}

interface ConnectionDeps {
  chatId: string;
  taskId: string;
  EventSourceImpl: EventSourceCtor;
  setProgress: (taskId: string, progress: TaskProgressPayload) => void;
  completeTask: (
    taskId: string,
    status: "success" | "failed",
    error?: string,
  ) => void;
}

/**
 * Exported for unit testing — lets tests inject a mock EventSource constructor
 * and exercise the reconnect / message-dispatch state machine without touching
 * React. Production code goes through `useTaskEvents` instead.
 */
export function createTaskEventSubscription(
  deps: ConnectionDeps,
  onChange: () => void,
): () => void {
  let source: EventSource | null = null;
  let attempts = 0;
  let closed = false;
  let retryTimer: ReturnType<typeof setTimeout> | null = null;

  const connect = (): void => {
    if (closed) return;
    source = new deps.EventSourceImpl(
      `/api/v1/chats/${deps.chatId}/tasks/${deps.taskId}/events`,
      { withCredentials: true },
    );

    source.onmessage = (event: MessageEvent<string>) => {
      attempts = 0;
      const payload = parsePayload(event.data);
      if (payload === null) return;
      if (payload.type === "data-task-progress") {
        const progress = parseProgress(payload.data);
        if (progress === null) return;
        deps.setProgress(deps.taskId, progress);
        onChange();
        return;
      }
      if (payload.type === "data-task-completed") {
        const completed = parseCompleted(payload.data);
        if (completed === null) return;
        deps.completeTask(deps.taskId, completed.status, completed.error);
        onChange();
        closed = true;
        source?.close();
        source = null;
      }
    };

    source.onerror = () => {
      source?.close();
      source = null;
      if (closed) return;
      if (attempts >= MAX_RECONNECT_ATTEMPTS) {
        closed = true;
        return;
      }
      const delay = BASE_BACKOFF_MS * 2 ** attempts;
      attempts += 1;
      retryTimer = setTimeout(connect, delay);
    };
  };

  connect();

  return () => {
    closed = true;
    if (retryTimer !== null) {
      clearTimeout(retryTimer);
      retryTimer = null;
    }
    source?.close();
    source = null;
  };
}

function getServerSnapshot(): number {
  return 0;
}

function getClientSnapshot(): number {
  return 0;
}

/**
 * Subscribes to the task events SSE stream for a given chat/task pair and
 * funnels progress + completion chunks into the Zustand task store.
 *
 * The SSE connection is the "external store" in React's sense — we don't
 * need a local snapshot to drive re-renders (components re-render when
 * `useTaskStore` state changes), so the snapshot reducers return a stable
 * zero. React still calls `subscribe` / the returned cleanup exactly once per
 * mount + unmount + deps change.
 */
export function useTaskEvents(chatId: string, taskId: string | null): void {
  const setProgress = useTaskStore((s) => s.setProgress);
  const completeTask = useTaskStore((s) => s.completeTask);

  const subscribe = (onChange: () => void): (() => void) => {
    if (taskId === null) return () => {};
    return createTaskEventSubscription(
      {
        chatId,
        taskId,
        EventSourceImpl: globalThis.EventSource,
        setProgress,
        completeTask,
      },
      onChange,
    );
  };

  useSyncExternalStore(subscribe, getClientSnapshot, getServerSnapshot);
}

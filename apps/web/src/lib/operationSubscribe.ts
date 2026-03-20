/**
 * Subscribe to a running operation's SSE event stream.
 *
 * Handles:
 * - Catchup events (buffered on server from before subscription)
 * - Live events (real-time as they arrive)
 * - Auto-reconnect with exponential backoff on disconnect
 * - Graceful cleanup on unsubscribe
 */

import { buildUrl, getAuthHeaders } from "@/lib/api/http";
import { parseSSEChunk } from "@/lib/sseParser";

export interface OperationSubscription {
  unsubscribe: () => void;
}

export interface SubscribeOptions<T> {
  /** Called for each SSE event (both catchup and live). */
  onEvent: (event: { type: string; data: T }) => void;
  /** Called when the operation completes (end event received). */
  onComplete?: () => void;
  /** Called on connection error. */
  onError?: (error: Error) => void;
  /** Event types that signal end-of-stream. */
  endEventTypes?: Set<string>;
  /** Max reconnect attempts. Default 10. */
  maxReconnects?: number;
}

export function subscribeToOperation<T = unknown>(
  operationId: string,
  options: SubscribeOptions<T>,
): OperationSubscription {
  const endTypes =
    options.endEventTypes ??
    new Set([
      "message_end",
      "experiment_end",
      "batch_complete",
      "batch_error",
      "benchmark_complete",
      "benchmark_error",
      "seed_complete",
    ]);
  const maxReconnects = options.maxReconnects ?? 10;
  const state: { aborted: boolean } = { aborted: false };
  /** Check if aborted (extracted to defeat ESLint's narrow-through-closure analysis). */
  const isAborted = () => state.aborted;
  let reconnectCount = 0;
  let controller = new AbortController();
  /** Last received SSE id — used to resume from this point on reconnect. */
  let lastEventId: string | undefined;

  async function connect(): Promise<void> {
    if (isAborted()) return;
    controller = new AbortController();

    try {
      const url = buildUrl(
        `/api/v1/operations/${operationId}/subscribe`,
        lastEventId != null && lastEventId !== "" ? { lastEventId } : undefined,
      );
      const resp = await fetch(url, {
        headers: {
          ...getAuthHeaders({ accept: "text/event-stream" }),
        },
        signal: controller.signal,
        credentials: "include",
      });

      if (!resp.ok) {
        if (resp.status === 404) {
          options.onError?.(new Error("Operation not found or already completed"));
          return;
        }
        throw new Error(`Subscribe failed: ${resp.status}`);
      }

      const reader = resp.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let buffer = "";
      reconnectCount = 0; // Reset on successful connection

      for (;;) {
        if (isAborted()) break;
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parsed = parseSSEChunk(buffer);
        buffer = parsed.rest;

        for (const evt of parsed.events) {
          if (evt.id != null && evt.id !== "") lastEventId = evt.id;

          if (isAborted()) return;

          try {
            const data = JSON.parse(evt.data) as T;
            options.onEvent({ type: evt.type, data });
          } catch (e) {
            console.warn("[subscribe] JSON parse error:", evt.type, evt.data, e);
          }

          if (endTypes.has(evt.type)) {
            reader.cancel().catch(() => {});
            options.onComplete?.();
            return;
          }
        }
      }
    } catch (err) {
      if (isAborted()) return;
      const error = err instanceof Error ? err : new Error(String(err));

      if (error.name === "AbortError") return;

      if (reconnectCount < maxReconnects) {
        reconnectCount++;
        const delay = Math.min(1000 * 2 ** (reconnectCount - 1), 30000);
        console.warn(
          `[subscribe] Reconnecting in ${delay}ms (attempt ${reconnectCount})`,
        );
        await new Promise<void>((r) => setTimeout(r, delay));
        if (isAborted()) return;
        return connect();
      }

      options.onError?.(error);
    }
  }

  // Start connecting.
  void connect();

  return {
    unsubscribe() {
      state.aborted = true;
      controller.abort();
    },
  };
}

interface ActiveOperation {
  operationId: string;
  streamId: string;
  type: string;
  status: string;
  createdAt: string | null;
}

/** Cancel a running operation on the backend. Fire-and-forget. */
export async function cancelOperation(operationId: string): Promise<void> {
  try {
    const url = buildUrl(`/api/v1/operations/${operationId}/cancel`);
    await fetch(url, {
      method: "POST",
      headers: getAuthHeaders(),
      credentials: "include",
    });
  } catch {
    // Best-effort — don't block the UI if the cancel request fails.
  }
}

/** Fetch list of active operations from the API. */
export async function fetchActiveOperations(filters?: {
  type?: string;
  streamId?: string;
}): Promise<ActiveOperation[]> {
  try {
    const params = new URLSearchParams();
    if (filters?.type != null && filters.type !== "") params.set("type", filters.type);
    if (filters?.streamId != null && filters.streamId !== "")
      params.set("streamId", filters.streamId);
    const qs = params.toString();
    const url = buildUrl(`/api/v1/operations/active${qs ? `?${qs}` : ""}`);
    const resp = await fetch(url, {
      headers: getAuthHeaders(),
      credentials: "include",
    });
    if (!resp.ok) return [];
    return (await resp.json()) as ActiveOperation[];
  } catch {
    return [];
  }
}

import { buildUrl, getAuthHeaders } from "@/lib/api/http";
import { streamSSE } from "@/lib/sse";
import type { ChatSSEEvent } from "./sse_events";
import { parseChatSSEEvent } from "./sse_events";
import { AppError } from "@/shared/errors/AppError";

export async function streamChat(
  message: string,
  siteId: string,
  options: {
    onMessage: (event: ChatSSEEvent) => void;
    onError?: (error: Error) => void;
    onComplete?: () => void;
    maxRetries?: number;
    retryDelay?: number;
  },
  context?: { strategyId?: string; planSessionId?: string },
  mode: "execute" | "plan" = "execute",
  signal?: AbortSignal,
) {
  // Fail fast if the API isn't ready (keeps retry loops clearer).
  const healthUrl = buildUrl("/health/ready");
  const health = await fetch(healthUrl, {
    headers: getAuthHeaders(undefined, { accept: "application/json" }),
  });
  if (!health.ok) {
    const err = new AppError(
      `API health check failed: HTTP ${health.status} (${healthUrl})`,
      "UNKNOWN",
    );
    options.onError?.(err);
    // If the caller didn't provide an error handler, preserve fail-fast behavior.
    if (!options.onError) throw err;
    return;
  }

  const { onMessage, ...rest } = options;
  try {
    await streamSSE(
      "/api/v1/chat",
      {
        method: "POST",
        body: {
          message,
          siteId,
          strategyId: context?.strategyId,
          planSessionId: context?.planSessionId,
          mode,
        },
        signal,
      },
      {
        ...rest,
        onEvent: (raw) => onMessage(parseChatSSEEvent(raw)),
      },
    );
  } catch (e) {
    // streamSSE already calls `onError`; avoid surfacing unhandled rejections from UI callers.
    if (!options.onError) {
      throw e;
    }
  }
}

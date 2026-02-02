import { buildUrl, getAuthHeaders } from "@/lib/api/http";
import { streamSSE } from "@/lib/sse";
import type { ChatSSEEvent } from "./sse_events";
import { parseChatSSEEvent } from "./sse_events";

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
  strategyId?: string
) {
  // Fail fast if the API isn't ready (keeps retry loops clearer).
  const healthUrl = buildUrl("/health/ready");
  const health = await fetch(healthUrl, {
    headers: getAuthHeaders(undefined, { accept: "application/json" }),
  });
  if (!health.ok) {
    throw new Error(`API health check failed: HTTP ${health.status} (${healthUrl})`);
  }

  const { onMessage, ...rest } = options;
  return streamSSE(
    "/api/v1/chat",
    {
      method: "POST",
      body: { message, siteId, strategyId },
    },
    {
      ...rest,
      onEvent: (raw) => onMessage(parseChatSSEEvent(raw)),
    }
  );
}


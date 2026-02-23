import { buildUrl, getAuthHeaders } from "@/lib/api/http";
import { streamSSE } from "@/lib/sse";
import type { ChatSSEEvent } from "./sse_events";
import { parseChatSSEEvent } from "./sse_events";
import { AppError } from "@/lib/errors/AppError";
import type { ChatMention, ModelSelection } from "@pathfinder/shared";

export interface StreamChatContext {
  strategyId?: string;
  planSessionId?: string;
  /** Legacy — prefer ``mentions`` instead. */
  referenceStrategyId?: string;
  /** @-mention references to strategies and experiments. */
  mentions?: ChatMention[];
}

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
  context?: StreamChatContext,
  mode: "execute" | "plan" = "execute",
  signal?: AbortSignal,
  modelSelection?: ModelSelection,
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
          referenceStrategyId: context?.referenceStrategyId,
          mentions: context?.mentions,
          mode,
          // Per-request model overrides
          provider: modelSelection?.provider,
          model: modelSelection?.model,
          reasoningEffort: modelSelection?.reasoningEffort,
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

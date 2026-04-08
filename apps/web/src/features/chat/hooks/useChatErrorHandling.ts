"use client";

import { useState } from "react";
import { APIError } from "@/lib/api/http";
import { toUserMessage } from "@/lib/api/errors";

/**
 * Centralised error handling for chat interactions.
 *
 * Detects 401 (session expired) and clears global session state;
 * for all other errors, surfaces a user-friendly message.
 */
export function useChatErrorHandling(
  setStrategyIdGlobal: (id: string | null) => void,
  clearMessages: () => void,
  setChatIsStreaming: (v: boolean) => void,
) {
  const [apiError, setApiError] = useState<string | null>(null);

  const handleError = (error: unknown, fallback: string) => {
    const isUnauthorized =
      error instanceof APIError
        ? error.status === 401
        : error instanceof Error && /HTTP 401\b/.test(error.message);
    if (isUnauthorized) {
      setStrategyIdGlobal(null);
      clearMessages();
      setChatIsStreaming(false);
      setApiError("Session expired. Please sign in again.");
      return;
    }
    setApiError(toUserMessage(error, fallback));
  };

  return { handleError, apiError, setApiError };
}

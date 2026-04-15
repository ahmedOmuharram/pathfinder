"use client";

import { useChat } from "@ai-sdk/react";

import type { PathfinderUIMessage } from "@pathfinder/shared";

import { logError } from "@/lib/telemetry/logError";

import { buildChatTransport } from "./transport";

export function useChatSession(
  chatId: string,
  mode: "strategy" | "experiment",
  initialMessages: PathfinderUIMessage[] = [],
) {
  const transport = buildChatTransport(mode);

  return useChat<PathfinderUIMessage>({
    id: chatId,
    messages: initialMessages,
    transport,
    onError: (error) => {
      // Surface the raw server-side error text to the devtools console so
      // the user can copy it when filing a bug, and ship it to telemetry.
      // The visible error banner is rendered from `session.error` in
      // ChatPanel/MessageList.
      console.error("[chat] stream error", error);
      logError(error, {
        source: "ai.useChat",
        extra: { "chat.id": chatId, "chat.mode": mode },
      });
    },
  });
}

import { DefaultChatTransport } from "ai";

import type { PathfinderUIMessage } from "@pathfinder/shared";

import { useSessionStore } from "@/state/useSessionStore";
import { useEngineStore } from "@/state/useEngineStore";

export function buildChatTransport(
  mode: "strategy" | "experiment",
): DefaultChatTransport<PathfinderUIMessage> {
  return new DefaultChatTransport<PathfinderUIMessage>({
    api: "/api/v1/chat",
    credentials: "include",
    headers: { "X-Requested-With": "XMLHttpRequest" },
    prepareSendMessagesRequest: ({ id, messages }) => ({
      body: {
        id,
        message: messages[messages.length - 1],
        metadata: {
          mode,
          siteId: useSessionStore.getState().selectedSite,
          pipeline: useEngineStore.getState().getPipelinePayload(),
        },
      },
    }),
  });
}

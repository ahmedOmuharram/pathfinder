"use client";

import { useQuery } from "@tanstack/react-query";
import { useEventCallback } from "usehooks-ts";

const AUTO_TRIGGER_PROMPT =
  "Please interpret these experiment results. Provide a clear scientific assessment, " +
  "explain what the metrics mean for this specific search, highlight key enrichment findings, " +
  "and suggest concrete next steps.";

interface UseWorkbenchChatAutoTriggerArgs {
  experimentId: string | null;
  historyLoaded: boolean;
  messageCount: number;
  streaming: boolean;
  sendMessage: (text: string) => void;
}

export function useWorkbenchChatAutoTrigger({
  experimentId,
  historyLoaded,
  messageCount,
  streaming,
  sendMessage,
}: UseWorkbenchChatAutoTriggerArgs): void {
  const stableSend = useEventCallback(sendMessage);

  useQuery({
    queryKey: ["workbench-auto-trigger", experimentId],
    queryFn: () => {
      stableSend(AUTO_TRIGGER_PROMPT);
      return { triggered: true };
    },
    enabled: experimentId != null && historyLoaded && messageCount === 0 && !streaming,
    staleTime: Infinity,
    gcTime: 0,
    retry: false,
  });
}

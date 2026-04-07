/**
 * Loads workbench chat message history from the API.
 *
 * Returns the loaded messages and a flag indicating whether loading
 * has completed. The caller (useWorkbenchChat) owns message state
 * via the shared chatMessageReducer and dispatches load_history.
 */

import { useQuery } from "@tanstack/react-query";
import { getWorkbenchChatMessages } from "../api/workbenchChatApi";
import type { WorkbenchMessage } from "./useWorkbenchChat";

interface UseWorkbenchChatHistoryReturn {
  historyMessages: WorkbenchMessage[];
  historyLoaded: boolean;
}

type RawChatMessage = Awaited<ReturnType<typeof getWorkbenchChatMessages>>[number];

function toWorkbenchMessage(
  m: RawChatMessage,
  index: number,
  experimentId: string,
): WorkbenchMessage {
  const msg: WorkbenchMessage = {
    id: m.messageId ?? `wb-hist-${experimentId}-${index}`,
    role: m.role,
    content: m.content,
  };
  if (m.toolCalls != null)
    msg.toolCalls = m.toolCalls as NonNullable<WorkbenchMessage["toolCalls"]>;
  if (m.citations != null)
    msg.citations = m.citations as NonNullable<WorkbenchMessage["citations"]>;
  return msg;
}

export function useWorkbenchChatHistory(
  experimentId: string | null,
): UseWorkbenchChatHistoryReturn {
  const { data, isFetched } = useQuery({
    queryKey: ["workbench-chat", "history", experimentId] as const,
    queryFn: async () => {
      const msgs = await getWorkbenchChatMessages(experimentId!);
      return msgs
        .filter((m) => m.content !== "")
        .map((m, i) => toWorkbenchMessage(m, i, experimentId!));
    },
    enabled: experimentId != null,
  });

  return {
    historyMessages: data ?? [],
    historyLoaded: experimentId == null || isFetched,
  };
}

/**
 * Loads workbench chat message history from the API.
 *
 * Separated from useWorkbenchChat so the history-loading concern
 * (fetch + transform + track loaded state) lives in its own hook.
 */

import { useState, useEffect, useRef } from "react";
import { getWorkbenchChatMessages } from "../api/workbenchChatApi";
import type { WorkbenchMessage } from "./useWorkbenchChat";

interface UseWorkbenchChatHistoryReturn {
  messages: WorkbenchMessage[];
  setMessages: React.Dispatch<React.SetStateAction<WorkbenchMessage[]>>;
  historyLoaded: boolean;
}

export function useWorkbenchChatHistory(
  experimentId: string | null,
): UseWorkbenchChatHistoryReturn {
  const [messages, setMessages] = useState<WorkbenchMessage[]>([]);
  const [loadedForId, setLoadedForId] = useState<string | null>(null);
  const historyLoaded = loadedForId === experimentId;

  const msgCounterRef = useRef(0);
  function nextMsgId(): string {
    return `wb-msg-${++msgCounterRef.current}`;
  }

  useEffect(() => {
    if (experimentId == null) return;

    let cancelled = false;
    getWorkbenchChatMessages(experimentId)
      .then((msgs) => {
        if (cancelled) return;
        const loaded: WorkbenchMessage[] = msgs
          .filter((m) => m.content !== "")
          .map((m) => {
            const msg: WorkbenchMessage = {
              id: m.messageId ?? nextMsgId(),
              role: m.role,
              content: m.content,
            };
            if (m.toolCalls != null)
              msg.toolCalls = m.toolCalls as NonNullable<WorkbenchMessage["toolCalls"]>;
            if (m.citations != null)
              msg.citations = m.citations as NonNullable<WorkbenchMessage["citations"]>;
            return msg;
          });
        setMessages(loaded);
        setLoadedForId(experimentId);
      })
      .catch((err) => {
        if (!cancelled) {
          console.error("[useWorkbenchChatHistory] Failed to load messages:", err);
        }
        if (!cancelled) setLoadedForId(experimentId);
      });

    return () => {
      cancelled = true;
    };
  }, [experimentId]);

  return { messages, setMessages, historyLoaded };
}

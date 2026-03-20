/**
 * Auto-triggers workbench chat interpretation on first open.
 *
 * Fires a sendMessage call when an experiment is opened for the first
 * time and there is no existing conversation history.
 */

import { useEffect, useRef } from "react";

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
  const autoTriggeredRef = useRef<string | null>(null);
  const sendMessageRef = useRef(sendMessage);

  useEffect(() => {
    sendMessageRef.current = sendMessage;
  }, [sendMessage]);

  useEffect(() => {
    if (experimentId == null) return;
    if (!historyLoaded) return;
    if (autoTriggeredRef.current === experimentId) return;
    if (messageCount > 0 || streaming) return;

    autoTriggeredRef.current = experimentId;
    sendMessageRef.current(AUTO_TRIGGER_PROMPT);
  }, [experimentId, historyLoaded, messageCount, streaming]);
}

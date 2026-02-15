import { useEffect } from "react";
import { useSessionStore } from "@/state/useSessionStore";

export function useChatPreviewUpdate(strategyId: string | null, messagesKey: string) {
  const bumpChatPreviewVersion = useSessionStore((s) => s.bumpChatPreviewVersion);

  useEffect(() => {
    if (!strategyId) return;
    bumpChatPreviewVersion();
  }, [strategyId, messagesKey, bumpChatPreviewVersion]);
}

import { useEffect } from "react";

export function useChatPreviewUpdate(strategyId: string | null, messagesKey: string) {
  useEffect(() => {
    if (!strategyId) return;
    if (typeof window === "undefined") return;
    window.dispatchEvent(
      new CustomEvent("chat-preview-update", { detail: { strategyId } }),
    );
  }, [strategyId, messagesKey]);
}

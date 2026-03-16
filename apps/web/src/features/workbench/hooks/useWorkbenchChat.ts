import { useState, useRef, useCallback, useEffect } from "react";
import type { ChatSSEEvent } from "@/lib/sse_events";
import type { Citation } from "@pathfinder/shared";
import { getWorkbenchChatMessages, streamWorkbenchChat } from "../api/workbenchChatApi";

export interface WorkbenchMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  toolCalls?: { id: string; name: string; result?: string }[];
}

interface ActiveToolCall {
  id: string;
  name: string;
}

export interface UseWorkbenchChatReturn {
  messages: WorkbenchMessage[];
  streaming: boolean;
  activeToolCalls: ActiveToolCall[];
  sendMessage: (text: string) => void;
  stop: () => void;
}

export function useWorkbenchChat(
  experimentId: string | null,
  siteId: string,
): UseWorkbenchChatReturn {
  const [messages, setMessages] = useState<WorkbenchMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [activeToolCalls, setActiveToolCalls] = useState<ActiveToolCall[]>([]);

  const cancelRef = useRef<(() => void) | null>(null);
  const autoTriggeredRef = useRef<string | null>(null);
  const currentAssistantIdRef = useRef<string | null>(null);

  const msgCounterRef = useRef(0);
  function nextMsgId(): string {
    return `wb-msg-${++msgCounterRef.current}`;
  }

  // Load existing messages on experiment change
  useEffect(() => {
    if (!experimentId) return;

    let cancelled = false;
    getWorkbenchChatMessages(experimentId)
      .then((msgs) => {
        if (cancelled) return;
        const loaded: WorkbenchMessage[] = msgs
          .filter((m) => m.role === "user" || m.role === "assistant")
          .filter((m) => m.content)
          .map((m) => ({
            id: m.messageId ?? nextMsgId(),
            role: m.role,
            content: m.content,
          }));
        setMessages(loaded);
      })
      .catch((err) => {
        if (!cancelled) {
          console.error("[useWorkbenchChat] Failed to load messages:", err);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [experimentId]);

  // Handle SSE events
  const handleEvent = useCallback((event: ChatSSEEvent) => {
    switch (event.type) {
      case "assistant_delta": {
        const delta = event.data.delta ?? "";
        if (!delta) return;
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.role === "assistant" && last.id === currentAssistantIdRef.current) {
            return [...prev.slice(0, -1), { ...last, content: last.content + delta }];
          }
          const id = nextMsgId();
          currentAssistantIdRef.current = id;
          return [...prev, { id, role: "assistant", content: delta }];
        });
        break;
      }
      case "assistant_message": {
        const content = event.data.content ?? "";
        if (!content) return;
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.role === "assistant" && last.id === currentAssistantIdRef.current) {
            return [...prev.slice(0, -1), { ...last, content }];
          }
          const id = nextMsgId();
          currentAssistantIdRef.current = id;
          return [...prev, { id, role: "assistant", content }];
        });
        break;
      }
      case "citations": {
        const citations = event.data.citations;
        if (!citations?.length) return;
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.role === "assistant") {
            return [...prev.slice(0, -1), { ...last, citations }];
          }
          return prev;
        });
        break;
      }
      case "tool_call_start":
        setActiveToolCalls((prev) => [
          ...prev,
          { id: event.data.id, name: event.data.name },
        ]);
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.role === "assistant" && last.id === currentAssistantIdRef.current) {
            const existing = last.toolCalls ?? [];
            return [
              ...prev.slice(0, -1),
              {
                ...last,
                toolCalls: [...existing, { id: event.data.id, name: event.data.name }],
              },
            ];
          }
          return prev;
        });
        break;
      case "tool_call_end":
        setActiveToolCalls((prev) => prev.filter((tc) => tc.id !== event.data.id));
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.role === "assistant" && last.toolCalls) {
            return [
              ...prev.slice(0, -1),
              {
                ...last,
                toolCalls: last.toolCalls.map((tc) =>
                  tc.id === event.data.id ? { ...tc, result: event.data.result } : tc,
                ),
              },
            ];
          }
          return prev;
        });
        break;
      case "message_end":
        setStreaming(false);
        setActiveToolCalls([]);
        currentAssistantIdRef.current = null;
        break;
      case "error":
        setStreaming(false);
        setActiveToolCalls([]);
        currentAssistantIdRef.current = null;
        break;
    }
  }, []);

  const sendMessage = useCallback(
    (text: string) => {
      if (!experimentId || streaming) return;

      // Cancel any existing stream
      cancelRef.current?.();

      // Add user message
      setMessages((prev) => [
        ...prev,
        { id: nextMsgId(), role: "user", content: text },
      ]);
      setStreaming(true);
      currentAssistantIdRef.current = null;

      const { cancel } = streamWorkbenchChat(experimentId, text, siteId, {
        onMessage: handleEvent,
        onError: (err) => {
          console.error("[useWorkbenchChat] Stream error:", err);
          setStreaming(false);
          setActiveToolCalls([]);
        },
        onComplete: () => {
          setStreaming(false);
          setActiveToolCalls([]);
        },
      });

      cancelRef.current = cancel;
    },
    [experimentId, siteId, streaming, handleEvent],
  );

  // Auto-interpretation: on first open with no conversation history
  const sendMessageRef = useRef(sendMessage);
  useEffect(() => {
    sendMessageRef.current = sendMessage;
  }, [sendMessage]);

  useEffect(() => {
    if (!experimentId) return;
    if (autoTriggeredRef.current === experimentId) return;
    // Only trigger if messages have been loaded (empty array) and not streaming
    if (messages.length > 0 || streaming) return;

    // Small delay to let messages load first
    const timer = setTimeout(() => {
      // Re-check after delay — messages might have loaded
      if (autoTriggeredRef.current === experimentId) return;
      autoTriggeredRef.current = experimentId;
      sendMessageRef.current(
        "Please interpret these experiment results. Provide a clear scientific assessment, " +
          "explain what the metrics mean for this specific search, highlight key enrichment findings, " +
          "and suggest concrete next steps.",
      );
    }, 500);

    return () => clearTimeout(timer);
  }, [experimentId, messages.length, streaming]);

  const stop = useCallback(() => {
    cancelRef.current?.();
    cancelRef.current = null;
    setStreaming(false);
    setActiveToolCalls([]);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cancelRef.current?.();
    };
  }, []);

  return { messages, streaming, activeToolCalls, sendMessage, stop };
}

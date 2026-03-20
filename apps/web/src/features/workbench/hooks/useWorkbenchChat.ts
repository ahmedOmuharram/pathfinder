import { useState, useRef, useCallback, useEffect } from "react";
import type { ChatSSEEvent } from "@/lib/sse_events";
import type { Citation } from "@pathfinder/shared";
import { cancelOperation } from "@/lib/operationSubscribe";
import { streamWorkbenchChat } from "../api/workbenchChatApi";
import { useWorkbenchStore } from "../store";
import { useWorkbenchChatHistory } from "./useWorkbenchChatHistory";
import { useWorkbenchChatAutoTrigger } from "./useWorkbenchChatAutoTrigger";

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

interface UseWorkbenchChatReturn {
  messages: WorkbenchMessage[];
  streaming: boolean;
  activeToolCalls: ActiveToolCall[];
  error: string | null;
  sendMessage: (text: string) => void;
  stop: () => void;
}

export function useWorkbenchChat(
  experimentId: string | null,
  siteId: string,
): UseWorkbenchChatReturn {
  // ---------------------------------------------------------------------------
  // History loading (separate concern)
  // ---------------------------------------------------------------------------
  const history = useWorkbenchChatHistory(experimentId);
  const { messages, setMessages, historyLoaded } = history;

  // ---------------------------------------------------------------------------
  // Streaming + event handling state
  // ---------------------------------------------------------------------------
  const [streaming, setStreaming] = useState(false);
  const [activeToolCalls, setActiveToolCalls] = useState<ActiveToolCall[]>([]);
  const [error, setError] = useState<string | null>(null);

  const cancelRef = useRef<(() => void) | null>(null);
  const operationIdRef = useRef<string | null>(null);
  const currentAssistantIdRef = useRef<string | null>(null);

  const msgCounterRef = useRef(0);
  function nextMsgId(): string {
    return `wb-msg-${++msgCounterRef.current}`;
  }

  // ---------------------------------------------------------------------------
  // SSE event handler
  // ---------------------------------------------------------------------------
  const handleEvent = useCallback(
    (event: ChatSSEEvent) => {
      switch (event.type) {
        case "assistant_delta": {
          const delta = event.data.delta ?? "";
          if (delta === "") return;
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (
              last?.role === "assistant" &&
              last.id === currentAssistantIdRef.current
            ) {
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
          if (content === "") return;
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (
              last?.role === "assistant" &&
              last.id === currentAssistantIdRef.current
            ) {
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
          if (citations == null || citations.length === 0) return;
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
            if (
              last?.role === "assistant" &&
              last.id === currentAssistantIdRef.current
            ) {
              const existing = last.toolCalls ?? [];
              return [
                ...prev.slice(0, -1),
                {
                  ...last,
                  toolCalls: [
                    ...existing,
                    { id: event.data.id, name: event.data.name },
                  ],
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
            if (last?.role === "assistant" && last.toolCalls != null) {
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
          setError(event.data.error !== "" ? event.data.error : "An error occurred");
          break;
        case "workbench_gene_set": {
          const gs = event.data.geneSet;
          if (gs != null) {
            useWorkbenchStore.getState().addGeneSet({
              id: gs.id,
              name: gs.name,
              geneCount: gs.geneCount,
              source: (["strategy", "paste", "upload", "derived", "saved"].includes(
                gs.source,
              )
                ? gs.source
                : "derived") as "strategy" | "paste" | "upload" | "derived" | "saved",
              siteId: gs.siteId,
              geneIds: [],
              createdAt: new Date().toISOString(),
              stepCount: 1,
            });
          }
          break;
        }
        case "message_start":
        case "user_message":
        case "planning_artifact":
        case "reasoning":
        case "subkani_task_start":
        case "subkani_tool_call_start":
        case "subkani_tool_call_end":
        case "subkani_task_end":
        case "strategy_update":
        case "graph_snapshot":
        case "strategy_link":
        case "strategy_meta":
        case "graph_cleared":
        case "optimization_progress":
        case "model_selected":
        case "graph_plan":
        case "executor_build_request":
        case "token_usage_partial":
        case "unknown":
          // These event types are handled elsewhere or are irrelevant to the workbench chat.
          break;
      }
    },
    [setMessages],
  );

  // ---------------------------------------------------------------------------
  // Send message
  // ---------------------------------------------------------------------------
  const sendMessage = useCallback(
    (text: string) => {
      if (experimentId == null || streaming) return;

      // Cancel any existing stream
      cancelRef.current?.();

      // Add user message
      setMessages((prev) => [
        ...prev,
        { id: nextMsgId(), role: "user", content: text },
      ]);
      setStreaming(true);
      setError(null);
      currentAssistantIdRef.current = null;

      const { promise, cancel } = streamWorkbenchChat(experimentId, text, siteId, {
        onMessage: handleEvent,
        onError: (err) => {
          console.error("[useWorkbenchChat] Stream error:", err);
          setStreaming(false);
          setActiveToolCalls([]);
          setError(err.message !== "" ? err.message : "An error occurred");
        },
        onComplete: () => {
          setStreaming(false);
          setActiveToolCalls([]);
          operationIdRef.current = null;
        },
      });

      cancelRef.current = cancel;
      void promise
        .then(({ operationId }) => {
          operationIdRef.current = operationId;
        })
        .catch(() => {
          // Error already handled by onError callback
        });
    },
    [experimentId, siteId, streaming, handleEvent, setMessages],
  );

  // ---------------------------------------------------------------------------
  // Auto-trigger (separate concern)
  // ---------------------------------------------------------------------------
  useWorkbenchChatAutoTrigger({
    experimentId,
    historyLoaded,
    messageCount: messages.length,
    streaming,
    sendMessage,
  });

  // ---------------------------------------------------------------------------
  // Stop + cleanup
  // ---------------------------------------------------------------------------
  const stop = useCallback(() => {
    cancelRef.current?.();
    cancelRef.current = null;
    if (operationIdRef.current != null) {
      void cancelOperation(operationIdRef.current);
      operationIdRef.current = null;
    }
    setStreaming(false);
    setActiveToolCalls([]);
  }, []);

  useEffect(() => {
    return () => {
      cancelRef.current?.();
    };
  }, []);

  return { messages, streaming, activeToolCalls, error, sendMessage, stop };
}

import { useState, useRef, useCallback, useEffect, useReducer } from "react";
import type { ChatSSEEvent } from "@/lib/sse_events";
import type { Citation } from "@pathfinder/shared";
import { cancelOperation } from "@/lib/operationSubscribe";
import { streamWorkbenchChat } from "../api/workbenchChatApi";
import { useInvalidateGeneSets } from "@/lib/query/hooks/useInvalidateGeneSets";
import { useWorkbenchChatHistory } from "./useWorkbenchChatHistory";
import { useWorkbenchChatAutoTrigger } from "./useWorkbenchChatAutoTrigger";
import {
  chatMessageReducer,
  initialChatMessageState,
} from "@/lib/chatMessageReducer";
import type { ChatMessageState, ChatMessageAction } from "@/lib/chatMessageReducer";

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

function createAssistantMessage(id: string, content: string): WorkbenchMessage {
  return { id, role: "assistant", content };
}

function createUserMessage(id: string, content: string): WorkbenchMessage {
  return { id, role: "user", content };
}

/**
 * Typed reducer wrapper — chatMessageReducer is generic, so we bind it
 * to WorkbenchMessage here to satisfy useReducer's signature.
 */
function workbenchReducer(
  state: ChatMessageState<WorkbenchMessage>,
  action: ChatMessageAction<WorkbenchMessage>,
): ChatMessageState<WorkbenchMessage> {
  return chatMessageReducer(state, action);
}

export function useWorkbenchChat(
  experimentId: string | null,
  siteId: string,
): UseWorkbenchChatReturn {
  // ---------------------------------------------------------------------------
  // Message state via shared reducer
  // ---------------------------------------------------------------------------
  const [state, dispatch] = useReducer(
    workbenchReducer,
    undefined,
    initialChatMessageState<WorkbenchMessage>,
  );

  // ---------------------------------------------------------------------------
  // History loading (separate concern)
  // ---------------------------------------------------------------------------
  const { historyLoaded, historyMessages } = useWorkbenchChatHistory(experimentId);

  // Track which experiment's history has been dispatched to the reducer.
  // Using useState (not useRef) so the synchronous dispatch-during-render
  // pattern satisfies the react-hooks/refs lint rule.
  const [loadedFor, setLoadedFor] = useState<string | null>(null);
  if (historyLoaded && loadedFor !== experimentId) {
    setLoadedFor(experimentId);
    dispatch({
      type: "load_history",
      messages: historyMessages,
      counterStart: historyMessages.length,
    });
  }

  // ---------------------------------------------------------------------------
  // Streaming + event handling state
  // ---------------------------------------------------------------------------
  const [streaming, setStreaming] = useState(false);
  const [activeToolCalls, setActiveToolCalls] = useState<ActiveToolCall[]>([]);
  const [error, setError] = useState<string | null>(null);
  const invalidateGeneSets = useInvalidateGeneSets();

  const cancelRef = useRef<(() => void) | null>(null);
  const operationIdRef = useRef<string | null>(null);

  // ---------------------------------------------------------------------------
  // SSE event handler
  // ---------------------------------------------------------------------------
  const handleEvent = useCallback(
    (event: ChatSSEEvent) => {
      switch (event.type) {
        case "assistant_delta":
          dispatch({
            type: "append_delta",
            delta: event.data.delta ?? "",
            createMessage: createAssistantMessage,
          });
          break;

        case "assistant_message":
          dispatch({
            type: "set_full_message",
            content: event.data.content ?? "",
            createMessage: createAssistantMessage,
          });
          break;

        case "citations":
          dispatch({
            type: "set_citations",
            citations: event.data.citations,
          });
          break;

        case "tool_call_start":
          setActiveToolCalls((prev) => [
            ...prev,
            { id: event.data.id, name: event.data.name },
          ]);
          dispatch({
            type: "start_tool_call",
            id: event.data.id,
            name: event.data.name,
          });
          break;

        case "tool_call_end":
          setActiveToolCalls((prev) => prev.filter((tc) => tc.id !== event.data.id));
          dispatch({
            type: "end_tool_call",
            id: event.data.id,
            result: event.data.result ?? "",
          });
          break;

        case "message_end":
          setStreaming(false);
          setActiveToolCalls([]);
          dispatch({ type: "end_stream" });
          break;

        case "error":
          setStreaming(false);
          setActiveToolCalls([]);
          dispatch({ type: "end_stream" });
          setError(event.data.error !== "" ? event.data.error : "An error occurred");
          break;

        case "workbench_gene_set": {
          const gs = event.data.geneSet;
          if (gs?.id != null && gs.name != null && gs.geneCount != null && gs.source != null && gs.siteId != null) {
            void invalidateGeneSets();
          }
          break;
        }
        case "message_start":
        case "user_message":
        case "planning_artifact":
        case "reasoning":
        case "strategy_update":
        case "graph_snapshot":
        case "strategy_link":
        case "strategy_meta":
        case "graph_cleared":
        case "optimization_progress":
        case "model_selected":
        case "graph_plan":
        case "token_usage_partial":
        case "planning_thought":
        case "plan_presented":
        case "plan_updated":
        case "decision_presented":
        case "phase_change":
        case "unknown":
          // These event types are handled elsewhere or are irrelevant to the workbench chat.
          break;
      }
    },
    [invalidateGeneSets],
  );

  // ---------------------------------------------------------------------------
  // Send message
  // ---------------------------------------------------------------------------
  const sendMessage = useCallback(
    (text: string) => {
      if (experimentId == null || streaming) return;

      // Cancel any existing stream
      cancelRef.current?.();

      // Add user message via reducer
      dispatch({
        type: "add_user_message",
        message: createUserMessage(`wb-msg-${state.msgCounter + 1}`, text),
      });
      setStreaming(true);
      setError(null);

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
    [experimentId, siteId, streaming, handleEvent, state.msgCounter],
  );

  // ---------------------------------------------------------------------------
  // Auto-trigger (separate concern)
  // ---------------------------------------------------------------------------
  useWorkbenchChatAutoTrigger({
    experimentId,
    historyLoaded,
    messageCount: state.messages.length,
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

  return { messages: state.messages, streaming, activeToolCalls, error, sendMessage, stop };
}

"use client";

import { useState, useRef, useEffect, useCallback, startTransition } from "react";
import { MessageComposer } from "@/features/chat/components/MessageComposer";
import { getStrategy, updateStrategy as updateStrategyApi } from "@/lib/api/client";
import type { Message, StrategyPlan, ToolCall } from "@pathfinder/shared";
import { useStrategyStore } from "@/state/useStrategyStore";
import { useSessionStore } from "@/state/useSessionStore";
import { useStrategyListStore } from "@/state/useStrategyListStore";
import type { StrategyWithMeta } from "@/types/strategy";
import { useThinkingState } from "@/features/chat/hooks/useThinkingState";
import { DraftSelectionBar } from "@/features/chat/components/DraftSelectionBar";
import { ChatMessageList } from "@/features/chat/components/ChatMessageList";
import { useLatestRef } from "@/shared/hooks/useLatestRef";
import { useChatPreviewUpdate } from "@/features/chat/hooks/useChatPreviewUpdate";
import { useChatAutoScroll } from "@/features/chat/hooks/useChatAutoScroll";
import { useConsumePendingAskNode } from "@/features/chat/hooks/useConsumePendingAskNode";
import { useResetOnStrategyChange } from "@/features/chat/hooks/useResetOnStrategyChange";
import { parseToolArguments } from "@/features/chat/utils/parseToolArguments";
import { parseToolResult } from "@/features/chat/utils/parseToolResult";
import { mergeMessages } from "@/features/chat/utils/mergeMessages";
import { useChatStreaming } from "@/features/chat/hooks/useChatStreaming";
import { useGraphSnapshot } from "@/features/chat/hooks/useGraphSnapshot";

interface ChatPanelProps {
  siteId: string;
  variant?: "full" | "compact";
  pendingAskNode?: Record<string, unknown> | null;
  onConsumeAskNode?: () => void;
}

export function ChatPanel({
  siteId,
  variant = "full",
  pendingAskNode = null,
  onConsumeAskNode,
}: ChatPanelProps) {
  const isCompact = variant === "compact";
  const [messages, setMessages] = useState<Message[]>([]);
  const thinking = useThinkingState();
  const [draftSelection, setDraftSelection] = useState<Record<string, unknown> | null>(
    null,
  );
  const [undoSnapshots, setUndoSnapshots] = useState<Record<number, StrategyWithMeta>>(
    {},
  );
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const pendingUndoSnapshotRef = useRef<StrategyWithMeta | null>(null);
  const currentStrategy = useStrategyStore((state) => state.strategy);
  const strategyRef = useLatestRef(currentStrategy);
  const previousStrategyIdRef = useRef<string | null>(null);
  const appliedSnapshotRef = useRef(false);
  const isStreamingRef = useRef(false);

  const applyThinkingPayload = thinking.applyThinkingPayload;
  const strategyId = useSessionStore((state) => state.strategyId);
  const setStrategyId = useSessionStore((state) => state.setStrategyId);
  const setChatIsStreaming = useSessionStore((state) => state.setChatIsStreaming);
  const pendingExecutorSend = useSessionStore((state) => state.pendingExecutorSend);
  const setPendingExecutorSend = useSessionStore(
    (state) => state.setPendingExecutorSend,
  );
  const selectedSiteDisplayName = useSessionStore(
    (state) => state.selectedSiteDisplayName,
  );
  const veupathdbSignedIn = useSessionStore((state) => state.veupathdbSignedIn);
  const veupathdbName = useSessionStore((state) => state.veupathdbName);
  const firstName = veupathdbName?.split(" ")[0];
  const displayName = selectedSiteDisplayName || siteId;
  const addStrategy = useStrategyListStore((state) => state.addStrategy);
  const addExecutedStrategy = useStrategyListStore(
    (state) => state.addExecutedStrategy,
  );

  // Strategy store for updating the graph
  const addStep = useStrategyStore((state) => state.addStep);
  const setStrategy = useStrategyStore((state) => state.setStrategy);
  const setWdkInfo = useStrategyStore((state) => state.setWdkInfo);
  const setStrategyMeta = useStrategyStore((state) => state.setStrategyMeta);
  const clearStrategy = useStrategyStore((state) => state.clear);
  const stepsById = useStrategyStore((state) => state.stepsById);

  const loadGraph = useCallback(
    (graphId: string) => {
      if (!graphId) return;
      getStrategy(graphId)
        .then((full) => {
          // If the stream already applied graph changes (strategy_update events),
          // don't overwrite the store – the live steps take precedence over the
          // potentially stale fetch result.
          if (appliedSnapshotRef.current) return;
          setStrategy(full);
          setStrategyMeta({
            name: full.name,
            recordType: full.recordType ?? undefined,
            siteId: full.siteId,
          });
        })
        .catch(() => {
          // Best-effort; keep existing graph if fetch fails.
        });
    },
    [setStrategy, setStrategyMeta],
  );

  const attachThinkingToLastAssistant = (
    calls: ToolCall[],
    activity?: { calls: Record<string, ToolCall[]>; status: Record<string, string> },
  ) => {
    if (calls.length === 0 && !activity) return;
    setMessages((prev) => {
      for (let i = prev.length - 1; i >= 0; i -= 1) {
        if (prev[i].role !== "assistant") continue;
        const hasTools = (prev[i].toolCalls?.length || 0) > 0;
        const hasActivity =
          Object.keys(prev[i].subKaniActivity?.calls || {}).length > 0;
        if (hasTools && hasActivity) return prev;
        const next = [...prev];
        next[i] = {
          ...prev[i],
          toolCalls: hasTools || calls.length === 0 ? prev[i].toolCalls : calls,
          subKaniActivity:
            hasActivity || !activity ? prev[i].subKaniActivity : activity,
        };
        return next;
      }
      return prev;
    });
  };

  const { applyGraphSnapshot } = useGraphSnapshot({
    siteId,
    strategyId,
    stepsById,
    strategyRef,
    pendingUndoSnapshotRef,
    appliedSnapshotRef,
    setStrategy,
    setStrategyMeta,
  });

  const { handleSendMessage, stopStreaming, isStreaming, apiError, setIsStreaming } =
    useChatStreaming({
      siteId,
      strategyId,
      draftSelection,
      setDraftSelection,
      thinking,
      setMessages,
      setUndoSnapshots,
      pendingUndoSnapshotRef,
      appliedSnapshotRef,
      loadGraph,
      addStrategy,
      addExecutedStrategy,
      setStrategyId,
      setWdkInfo,
      setStrategy,
      setStrategyMeta,
      clearStrategy,
      addStep,
      parseToolArguments,
      parseToolResult,
      applyGraphSnapshot,
      getStrategy,
      strategyRef,
      currentStrategy,
      attachThinkingToLastAssistant,
      mode: "execute",
    });

  // Send any queued executor message once we're ready (avoids races while switching tabs/strategy).
  useEffect(() => {
    if (!pendingExecutorSend) return;
    if (!strategyId) return;
    if (pendingExecutorSend.strategyId !== strategyId) return;
    if (isStreamingRef.current) return;
    const msg = (pendingExecutorSend.message || "").trim();
    if (!msg) {
      setPendingExecutorSend(null);
      return;
    }
    // Programmatic send: also clear the composer input (since MessageComposer manages
    // its own local state and won't auto-clear when we send outside of it).
    handleSendMessage(msg);
    window.dispatchEvent(
      new CustomEvent("pathfinder:prefill-composer", {
        detail: { mode: "execute", message: "" },
      }),
    );
    setPendingExecutorSend(null);
  }, [pendingExecutorSend, strategyId, handleSendMessage, setPendingExecutorSend]);

  useEffect(() => {
    isStreamingRef.current = isStreaming;
  }, [isStreaming]);

  useEffect(() => {
    setChatIsStreaming(isStreaming);
  }, [isStreaming, setChatIsStreaming]);

  useChatPreviewUpdate(strategyId, `${messages.length}`);

  useResetOnStrategyChange({
    strategyId,
    isStreamingRef,
    previousStrategyIdRef,
    resetThinking: thinking.reset,
    setIsStreaming,
    setMessages,
    setUndoSnapshots,
    pendingUndoSnapshotRef,
  });

  useChatAutoScroll(messagesEndRef, `${messages.length}:${isStreaming ? "s" : "i"}`);

  useEffect(() => {
    if (!strategyId) {
      if (isStreaming) {
        return;
      }
      startTransition(() => {
        setMessages([]);
      });
      return;
    }
    if (isStreaming) {
      return;
    }
    getStrategy(strategyId)
      .then((strategy) => {
        setMessages((prev) => mergeMessages(prev, strategy.messages || []));
        if (!isStreaming && strategy.thinking) {
          if (applyThinkingPayload(strategy.thinking)) {
            setIsStreaming(true);
          }
        }
        if (strategy.id && !appliedSnapshotRef.current) {
          loadGraph(strategy.id);
        }
      })
      .catch(() => {
        // Keep local messages if fetch fails.
      });
  }, [strategyId, isStreaming, applyThinkingPayload, loadGraph, setIsStreaming]);

  useConsumePendingAskNode({
    enabled: !isCompact,
    pendingAskNode,
    setDraftSelection,
    onConsumeAskNode,
  });

  return (
    <div
      className={`flex h-full flex-col bg-white ${isCompact ? "text-[11px]" : "text-[13px]"}`}
    >
      {/* Messages area */}
      <ChatMessageList
        isCompact={isCompact}
        siteId={siteId}
        displayName={displayName}
        firstName={firstName}
        signedIn={veupathdbSignedIn}
        mode="execute"
        isStreaming={isStreaming}
        messages={messages}
        undoSnapshots={undoSnapshots}
        onSend={handleSendMessage}
        onUndoSnapshot={(snapshot) => {
          setStrategy(snapshot);
          setStrategyMeta({
            name: snapshot.name,
            description: snapshot.description ?? undefined,
            recordType: snapshot.recordType ?? undefined,
          });
        }}
        onApplyPlanningArtifact={async (artifact) => {
          if (!strategyId) return;
          const proposed = artifact.proposedStrategyPlan;
          if (!proposed || typeof proposed !== "object" || Array.isArray(proposed))
            return;
          try {
            await updateStrategyApi(strategyId, { plan: proposed as StrategyPlan });
            const full = await getStrategy(strategyId);
            setStrategy(full);
            setStrategyMeta({
              name: full.name,
              description: full.description ?? undefined,
              recordType: full.recordType ?? undefined,
              siteId: full.siteId,
            });
          } catch {
            // Best-effort; if apply fails we keep existing strategy state.
          }
        }}
        thinking={thinking}
        messagesEndRef={messagesEndRef}
      />

      {/* Message composer */}
      {!isCompact && (
        <div className="border-t border-slate-200 bg-white p-3">
          {apiError && (
            <div className="mb-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
              {apiError}
            </div>
          )}
          {draftSelection && (
            <DraftSelectionBar
              selection={draftSelection}
              onRemove={() => setDraftSelection(null)}
            />
          )}
          <div className="flex items-center gap-3">
            <div className="flex-1">
              <MessageComposer
                onSend={handleSendMessage}
                disabled={isStreaming}
                isStreaming={isStreaming}
                onStop={stopStreaming}
                mode="execute"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

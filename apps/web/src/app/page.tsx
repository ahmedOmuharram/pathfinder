"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import { ChatPanel } from "@/features/chat/components/ChatPanel";
import { PlanPanel } from "@/features/chat/components/PlanPanel";
import { StrategyGraph } from "@/features/strategy/graph/components/StrategyGraph";
import { SitePicker } from "@/features/sites/components/SitePicker";
import { useSessionStore } from "@/state/useSessionStore";
import { useStrategyStore } from "@/state/useStrategyStore";
import { StrategySidebar } from "@/features/sidebar/components/StrategySidebar";
import { PlansSidebar } from "@/features/sidebar/components/PlansSidebar";
import { useStrategyListStore } from "@/state/useStrategyListStore";
import { getStrategy } from "@/lib/api/client";
import type { Message } from "@pathfinder/shared";
import { ToastContainer } from "@/app/components/ToastContainer";
import { useToasts } from "@/app/hooks/useToasts";
import { useSidebarResize } from "@/app/hooks/useSidebarResize";
import { useActiveView } from "@/app/hooks/useActiveView";
import { useBuildStrategy } from "@/app/hooks/useBuildStrategy";

export default function HomePage() {
  const { selectedSite, setSelectedSite } = useSessionStore();
  const chatMode = useSessionStore((state) => state.chatMode);
  const setChatMode = useSessionStore((state) => state.setChatMode);
  const chatIsStreaming = useSessionStore((state) => state.chatIsStreaming);
  const setStrategyId = useSessionStore((state) => state.setStrategyId);
  const selectedSiteDisplayName = useSessionStore(
    (state) => state.selectedSiteDisplayName,
  );
  const veupathdbSignedIn = useSessionStore((state) => state.veupathdbSignedIn);
  const strategyId = useSessionStore((state) => state.strategyId);
  const { strategy } = useStrategyStore();
  const buildPlan = useStrategyStore((state) => state.buildPlan);
  const clearStrategy = useStrategyStore((state) => state.clear);
  const setStrategyMeta = useStrategyStore((state) => state.setStrategyMeta);
  const setWdkInfo = useStrategyStore((state) => state.setWdkInfo);
  const addExecutedStrategy = useStrategyListStore(
    (state) => state.addExecutedStrategy,
  );
  const strategies = useStrategyListStore((state) => state.strategies);

  const { toasts, addToast, removeToast, durationMs } = useToasts();
  const { activeView, setActiveView, toggleView } = useActiveView("chat");
  const { layoutRef, sidebarWidth, startDragging } = useSidebarResize();
  const [previewMessages, setPreviewMessages] = useState<Message[]>([]);
  const [pendingAskNode, setPendingAskNode] = useState<Record<string, unknown> | null>(
    null,
  );

  const [isHydrated, setIsHydrated] = useState(false);
  const lastSiteRef = useRef<string | null>(null);

  useEffect(() => {
    setIsHydrated(true);
  }, []);

  useEffect(() => {
    if (!isHydrated) return;
    if (lastSiteRef.current && lastSiteRef.current !== selectedSite) {
      setStrategyId(null);
      clearStrategy();
      setActiveView("chat");
    }
    lastSiteRef.current = selectedSite;
  }, [selectedSite, isHydrated, setStrategyId, clearStrategy, setActiveView]);

  useEffect(() => {
    if (!isHydrated) return;
    if (chatMode !== "execute") return;
    if (strategyId) return;
    const latest = strategies.find((c) => c.siteId === selectedSite);
    if (latest) {
      setStrategyId(latest.id);
    }
  }, [isHydrated, chatMode, strategyId, strategies, selectedSite, setStrategyId]);

  useEffect(() => {
    const handleAskNode = (event: Event) => {
      const detail = (event as CustomEvent).detail as
        | Record<string, unknown>
        | undefined;
      if (detail) {
        setPendingAskNode(detail);
        setActiveView("chat");
      }
    };
    window.addEventListener("pathfinder:ask-node", handleAskNode);
    return () => window.removeEventListener("pathfinder:ask-node", handleAskNode);
  }, [setActiveView]);

  useEffect(() => {
    const handler = () => {
      setActiveView("chat");
    };
    window.addEventListener("pathfinder:open-executor-chat", handler);
    return () => window.removeEventListener("pathfinder:open-executor-chat", handler);
  }, [setActiveView]);

  useEffect(() => {
    if (chatMode !== "execute") return;
    if (!strategyId) {
      setPreviewMessages([]);
      return;
    }
    let cancelled = false;
    const loadPreview = async () => {
      try {
        const strategy = await getStrategy(strategyId);
        if (cancelled) return;
        const preview = strategy.messages?.slice(-5) ?? [];
        setPreviewMessages(preview);
      } catch {
        if (!cancelled) {
          setPreviewMessages([]);
        }
      }
    };
    void loadPreview();
    const previewHandler = (event: Event) => {
      const custom = event as CustomEvent<{ strategyId?: string }>;
      if (custom.detail?.strategyId === strategyId) {
        void loadPreview();
      }
    };
    window.addEventListener("chat-preview-update", previewHandler);
    return () => {
      cancelled = true;
      window.removeEventListener("chat-preview-update", previewHandler);
    };
  }, [chatMode, strategyId]);

  const activeStrategy = strategy;

  const planResult = buildPlan();
  const canBuild = !!planResult;
  const { isBuilding, handleBuild } = useBuildStrategy({
    selectedSite,
    selectedSiteDisplayName,
    strategy,
    planResult,
    veupathdbSignedIn,
    addExecutedStrategy,
    setStrategyMeta,
    setWdkInfo,
    addToast,
  });

  if (!isHydrated) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-50 text-slate-500">
        <div className="text-sm">Loading...</div>
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col bg-slate-50 text-slate-900">
      <ToastContainer toasts={toasts} durationMs={durationMs} onDismiss={removeToast} />
      <div className="border-b border-slate-200 bg-white px-5 py-3">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Image src="/pathfinder.svg" alt="PathFinder" width={32} height={32} />
            <div>
              <div className="text-base font-semibold tracking-tight text-slate-900">
                PathFinder
              </div>
              <div className="text-[10px] uppercase tracking-wider text-slate-500">
                VEuPathDB Strategy Builder
              </div>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <SitePicker
              value={selectedSite}
              onChange={setSelectedSite}
              showSelect={false}
              showVisit={false}
              showAuth
              layout="inline"
            />
          </div>
        </div>
      </div>

      <div ref={layoutRef} className="flex min-h-0 flex-1 overflow-hidden">
        <div
          className="shrink-0 border-r border-slate-200 bg-white"
          style={{ width: sidebarWidth }}
        >
          <div className="relative h-full">
            <div className="h-full pb-44">
              {chatMode === "plan" ? (
                <PlansSidebar siteId={selectedSite} />
              ) : (
                <StrategySidebar
                  siteId={selectedSite}
                  onToast={addToast}
                  onOpenStrategy={(source) =>
                    setActiveView(source === "new" ? "chat" : "graph")
                  }
                />
              )}
            </div>
            {chatMode === "execute" && (
              <div className="absolute bottom-4 left-4 right-4 z-20">
                <div
                  role="button"
                  tabIndex={0}
                  onClick={toggleView}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      toggleView();
                    }
                  }}
                  className="group rounded-lg border border-slate-200 bg-white/90 p-2 shadow-sm backdrop-blur transition hover:border-slate-300 hover:bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-300"
                >
                  <div className="flex items-center justify-between text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                    <span>
                      {activeView === "chat" ? "Graph preview" : "Chat preview"}
                    </span>
                    <span className="text-slate-400 group-hover:text-slate-600">
                      Click to switch
                    </span>
                  </div>
                  <div className="relative mt-2 h-28 w-full overflow-hidden rounded-md border border-slate-200 bg-slate-50">
                    <div
                      className="pointer-events-none absolute inset-0"
                      style={{
                        transform: "scale(0.5)",
                        transformOrigin: "top left",
                        width: "200%",
                        height: "200%",
                      }}
                    >
                      {activeView === "chat" ? (
                        <StrategyGraph
                          strategy={activeStrategy}
                          siteId={selectedSite}
                          variant="compact"
                        />
                      ) : (
                        <div className="flex h-full w-full flex-col justify-center gap-2 p-2">
                          <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                            Chat preview
                          </div>
                          {previewMessages.length === 0 ? (
                            <div className="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] text-slate-400">
                              No messages yet
                            </div>
                          ) : (
                            <div className="space-y-1">
                              {previewMessages.slice(-3).map((message, idx) => (
                                <div
                                  key={`${message.timestamp}-${idx}`}
                                  className="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px]"
                                >
                                  <div className="text-[9px] font-semibold uppercase tracking-wide text-slate-400">
                                    {message.role}
                                  </div>
                                  <div className="line-clamp-2 text-slate-600">
                                    {message.content}
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
        <div
          onMouseDown={startDragging}
          className="w-1 cursor-col-resize bg-slate-100 hover:bg-slate-200"
        />
        <div className="relative flex min-h-0 min-w-0 flex-1 flex-col bg-white">
          <div className="border-b border-slate-200 bg-white p-3">
            <div className="grid w-full grid-cols-2 overflow-hidden rounded-md border border-slate-200">
              <button
                type="button"
                onClick={() => setChatMode("plan")}
                disabled={chatIsStreaming}
                data-testid="mode-toggle-plan"
                className={`px-3 py-2 text-[12px] font-semibold transition-colors ${
                  chatMode === "plan"
                    ? "bg-slate-900 text-white"
                    : "bg-white text-slate-700 hover:bg-slate-50"
                }`}
                aria-pressed={chatMode === "plan"}
              >
                Ask & Plan
              </button>
              <button
                type="button"
                onClick={() => setChatMode("execute")}
                disabled={chatIsStreaming}
                data-testid="mode-toggle-execute"
                className={`px-3 py-2 text-[12px] font-semibold transition-colors ${
                  chatMode === "execute"
                    ? "bg-slate-900 text-white"
                    : "bg-white text-slate-700 hover:bg-slate-50"
                }`}
                aria-pressed={chatMode === "execute"}
              >
                Create Strategy
              </button>
            </div>
          </div>

          {chatMode === "plan" ? (
            <div className="min-h-0 flex-1">
              <PlanPanel siteId={selectedSite} />
            </div>
          ) : (
            <>
              <div className={activeView === "chat" ? "min-h-0 flex-1" : "hidden"}>
                <ChatPanel
                  siteId={selectedSite}
                  pendingAskNode={pendingAskNode}
                  onConsumeAskNode={() => setPendingAskNode(null)}
                />
              </div>
              <div className={activeView === "graph" ? "min-h-0 flex-1" : "hidden"}>
                <StrategyGraph
                  strategy={activeStrategy}
                  siteId={selectedSite}
                  onPush={handleBuild}
                  canPush={canBuild && veupathdbSignedIn}
                  isPushing={isBuilding}
                  pushLabel={`Push to ${selectedSiteDisplayName}`}
                  pushDisabledReason={
                    !veupathdbSignedIn
                      ? "Log in to VEuPathDB to push strategies."
                      : undefined
                  }
                  onToast={addToast}
                />
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

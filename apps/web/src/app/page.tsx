"use client";

import { useCallback, useEffect, useState } from "react";
import { usePrevious } from "@/lib/hooks/usePrevious";
import { UnifiedChatPanel } from "@/features/chat/components/UnifiedChatPanel";
import { StrategyGraph } from "@/features/strategy/graph/components/StrategyGraph";
import { ConversationSidebar } from "@/features/sidebar/components/ConversationSidebar";
import { useSessionStore } from "@/state/useSessionStore";
import { useStrategyStore } from "@/state/useStrategyStore";
import { useStrategyListStore } from "@/state/useStrategyListStore";
import { refreshAuth } from "@/lib/api/client";
import { ToastContainer } from "@/app/components/ToastContainer";
import { LoginGate } from "@/app/components/LoginGate";
import { TopBar } from "@/app/components/TopBar";
import { Modal } from "@/lib/components/Modal";
import { useToasts } from "@/app/hooks/useToasts";
import { useSidebarResize } from "@/app/hooks/useSidebarResize";
import { useBuildStrategy } from "@/features/strategy/hooks/useBuildStrategy";
import { FlaskConical, Settings, X } from "lucide-react";
import Link from "next/link";
import { CompactStrategyView } from "@/features/strategy/graph/components/CompactStrategyView";
import { SettingsPage } from "@/features/settings/components/SettingsPage";

export default function HomePage() {
  const { selectedSite, setSelectedSite } = useSessionStore();
  const setStrategyId = useSessionStore((state) => state.setStrategyId);
  const selectedSiteDisplayName = useSessionStore(
    (state) => state.selectedSiteDisplayName,
  );
  const veupathdbSignedIn = useSessionStore((state) => state.veupathdbSignedIn);
  const setAuthToken = useSessionStore((state) => state.setAuthToken);
  const strategyId = useSessionStore((state) => state.strategyId);
  const { strategy } = useStrategyStore();
  const buildPlan = useStrategyStore((state) => state.buildPlan);
  const clearStrategy = useStrategyStore((state) => state.clear);
  const setStrategyMeta = useStrategyStore((state) => state.setStrategyMeta);
  const setWdkInfo = useStrategyStore((state) => state.setWdkInfo);
  const addExecutedStrategy = useStrategyListStore(
    (state) => state.addExecutedStrategy,
  );

  const { toasts, addToast, removeToast, durationMs } = useToasts();
  const { layoutRef, sidebarWidth, startDragging } = useSidebarResize();
  const [pendingSiteChange, setPendingSiteChange] = useState<string | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [graphEditing, setGraphEditing] = useState(false);
  const pendingAskNode = useSessionStore((state) => state.pendingAskNode);
  const setPendingAskNode = useSessionStore((state) => state.setPendingAskNode);

  const prevSite = usePrevious(selectedSite);

  useEffect(() => {
    if (prevSite && prevSite !== selectedSite) {
      setStrategyId(null);
      clearStrategy();
    }
  }, [selectedSite, prevSite, setStrategyId, clearStrategy]);

  /** Intercept site changes: confirm if there's an active strategy to avoid data loss. */
  const handleSiteChange = useCallback(
    (nextSite: string) => {
      if (nextSite === selectedSite) return;
      if (strategy && strategy.steps.length > 0) {
        setPendingSiteChange(nextSite);
        return;
      }
      setSelectedSite(nextSite);
    },
    [selectedSite, strategy, setSelectedSite],
  );

  const confirmSiteChange = useCallback(() => {
    if (pendingSiteChange) {
      setSelectedSite(pendingSiteChange);
      setPendingSiteChange(null);
    }
  }, [pendingSiteChange, setSelectedSite]);

  // Re-derive the internal pathfinder-auth token from the live VEuPathDB session.
  const authRefreshed = useSessionStore((state) => state.authRefreshed);
  const setAuthRefreshed = useSessionStore((state) => state.setAuthRefreshed);
  useEffect(() => {
    if (!veupathdbSignedIn) return;
    if (authRefreshed) return;
    setAuthRefreshed(true);
    refreshAuth()
      .then((result) => {
        if (result.authToken) setAuthToken(result.authToken);
      })
      .catch(() => {
        setAuthToken(null);
      });
  }, [veupathdbSignedIn, authRefreshed, setAuthRefreshed, setAuthToken]);

  const hasGraph = !!(strategy && strategy.steps.length > 0);

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

  // Login gate
  if (!veupathdbSignedIn) {
    return <LoginGate selectedSite={selectedSite} onSiteChange={handleSiteChange} />;
  }

  return (
    <div className="flex h-full flex-col bg-slate-50 text-slate-900">
      <ToastContainer toasts={toasts} durationMs={durationMs} onDismiss={removeToast} />

      {/* Top bar with settings gear */}
      <TopBar
        selectedSite={selectedSite}
        onSiteChange={handleSiteChange}
        actions={
          <div className="flex items-center gap-2">
            <Link
              href="/experiments"
              className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 px-2.5 py-1.5 text-[11px] font-medium text-slate-600 transition hover:border-slate-300 hover:bg-slate-50"
            >
              <FlaskConical className="h-3.5 w-3.5" aria-hidden />
              Experiments
            </Link>
            <button
              type="button"
              onClick={() => setShowSettings(true)}
              className="rounded-md border border-slate-200 p-2 text-slate-500 transition hover:border-slate-300 hover:text-slate-700"
              aria-label="Settings"
              title="Settings"
            >
              <Settings className="h-4 w-4" aria-hidden />
            </button>
          </div>
        }
      />

      <div ref={layoutRef} className="flex min-h-0 flex-1 overflow-hidden">
        {/* Unified conversation sidebar */}
        <div
          className="flex shrink-0 flex-col border-r border-slate-200 bg-white"
          style={{ width: sidebarWidth }}
        >
          <ConversationSidebar siteId={selectedSite} onToast={addToast} />
        </div>

        <div
          onMouseDown={startDragging}
          className="w-1 cursor-col-resize bg-slate-100 hover:bg-slate-200"
        />

        {/* Main content: unified chat + collapsible graph */}
        <div className="relative flex min-h-0 min-w-0 flex-1 flex-col bg-white">
          {/* Unified chat panel (always visible) */}
          <div className="min-h-0 flex-1">
            <UnifiedChatPanel
              siteId={selectedSite}
              pendingAskNode={pendingAskNode}
              onConsumeAskNode={() => setPendingAskNode(null)}
            />
          </div>

          {/* Compact strategy strip (always visible when graph exists) */}
          {hasGraph && (
            <CompactStrategyView
              strategy={strategy}
              onEditGraph={() => setGraphEditing(true)}
            />
          )}

          {/* Graph editor modal (near-fullscreen) */}
          <Modal
            open={graphEditing}
            onClose={() => setGraphEditing(false)}
            title="Graph Editor"
            maxWidth="max-w-[95vw]"
          >
            <div className="flex h-[90vh] flex-col overflow-hidden rounded-lg">
              <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50 px-4 py-2">
                <span className="text-[12px] font-semibold uppercase tracking-wider text-slate-500">
                  Graph Editor
                </span>
                <button
                  type="button"
                  onClick={() => setGraphEditing(false)}
                  className="inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-[11px] font-medium text-slate-500 transition hover:bg-slate-100 hover:text-slate-700"
                >
                  <X className="h-3.5 w-3.5" aria-hidden />
                  Close
                </button>
              </div>
              <div className="min-h-0 flex-1">
                <StrategyGraph
                  strategy={strategy}
                  siteId={selectedSite}
                  onToast={addToast}
                />
              </div>
            </div>
          </Modal>
        </div>
      </div>

      {/* Site change confirmation modal */}
      <Modal
        open={!!pendingSiteChange}
        onClose={() => setPendingSiteChange(null)}
        title="Switch site?"
        maxWidth="max-w-sm"
      >
        <div className="px-5 pb-5 pt-2">
          <p className="text-[13px] text-slate-600">
            Your current strategy will be cleared when you switch sites. Are you sure
            you want to continue?
          </p>
          <div className="mt-4 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setPendingSiteChange(null)}
              className="rounded-md border border-slate-200 px-3 py-1.5 text-[12px] font-medium text-slate-700 transition hover:bg-slate-50"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={confirmSiteChange}
              className="rounded-md bg-slate-900 px-3 py-1.5 text-[12px] font-medium text-white transition hover:bg-slate-800"
            >
              Switch site
            </button>
          </div>
        </div>
      </Modal>

      {/* Settings modal */}
      <SettingsPage
        open={showSettings}
        onClose={() => setShowSettings(false)}
        siteId={selectedSite}
      />
    </div>
  );
}

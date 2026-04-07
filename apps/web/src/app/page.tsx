"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { usePrevious } from "@/lib/hooks/usePrevious";
import { UnifiedChatPanel } from "@/features/chat/components/UnifiedChatPanel";
import { ConversationSidebar } from "@/features/sidebar/components/ConversationSidebar";
import { useSessionStore } from "@/state/useSessionStore";
import { useStrategyStore } from "@/state/strategy/store";

import { ToastContainer } from "@/app/components/ToastContainer";
import { LoginModal } from "@/app/components/LoginModal";
import { TopBar } from "@/app/components/TopBar";
import { TopBarActions } from "@/app/components/TopBarActions";
import { EmbeddedToolbar } from "@/app/components/EmbeddedToolbar";
import { GraphEditorModal } from "@/app/components/GraphEditorModal";
import { LoadingScreen } from "@/app/components/LoadingScreen";
import { ApiErrorScreen } from "@/app/components/ApiErrorScreen";
import { useToasts } from "@/app/hooks/useToasts";
import { useSidebarResize } from "@/app/hooks/useSidebarResize";
import { useModalState } from "@/app/hooks/useModalState";
import { useGeneSetExport } from "@/app/hooks/useGeneSetExport";
import { CompactStrategyView } from "@/features/strategy/graph/components/CompactStrategyView";
import { SettingsPage } from "@/features/settings/components/SettingsPage";
import { useAuthCheck } from "@/app/hooks/useAuthCheck";
import { useAuthRefresh } from "@/app/hooks/useAuthRefresh";
import { useSystemConfig } from "@/app/hooks/useSystemConfig";
import { SetupRequiredScreen } from "@/app/components/SetupRequiredScreen";
import { useSiteTheme } from "@/features/sites/hooks/useSiteTheme";
import { useStableGraph } from "@/app/hooks/useStableGraph";
import { PlanPanel } from "@/features/chat/components/plan/PlanPanel";
import { usePlanStore } from "@/state/usePlanStore";
import { ClipboardList } from "lucide-react";

export default function HomePage() {
  return (
    <Suspense>
      <HomePageInner />
    </Suspense>
  );
}

function HomePageInner() {
  const searchParams = useSearchParams();
  const embedded = searchParams.get("embedded") === "true";
  const siteIdParam = searchParams.get("siteId");

  const { selectedSite, setSelectedSite } = useSessionStore();
  const setStrategyId = useSessionStore((state) => state.setStrategyId);
  const veupathdbSignedIn = useSessionStore((state) => state.veupathdbSignedIn);
  const { authLoading, apiError, retry: retryAuth } = useAuthCheck();
  const { configLoading, setupRequired, retry: retryConfig } = useSystemConfig();
  useSiteTheme(selectedSite);
  useAuthRefresh();
  const strategy = useStrategyStore((state) => state.strategy);
  const clearStrategy = useStrategyStore((state) => state.clear);

  const { toasts, addToast, removeToast, durationMs } = useToasts();
  const { layoutRef, sidebarWidth, startDragging } = useSidebarResize();
  const modals = useModalState();
  const pendingAskNode = useSessionStore((state) => state.pendingAskNode);
  const setPendingAskNode = useSessionStore((state) => state.setPendingAskNode);

  const prevSite = usePrevious(selectedSite);

  // Lock to a specific site when embedded with a siteId param
  useEffect(() => {
    if (siteIdParam !== null && siteIdParam !== selectedSite) {
      setSelectedSite(siteIdParam);
    }
  }, [siteIdParam, selectedSite, setSelectedSite]);

  useEffect(() => {
    if (prevSite !== undefined && prevSite !== selectedSite) {
      setStrategyId(null);
      clearStrategy();
    }
  }, [selectedSite, prevSite, setStrategyId, clearStrategy]);

  const handleSiteChange = useCallback(
    (nextSite: string) => {
      if (nextSite === selectedSite) return;
      setSelectedSite(nextSite);
    },
    [selectedSite, setSelectedSite],
  );

  // --- Workbench gene set export ---
  const { exportingGeneSet, handleExportAsGeneSet } = useGeneSetExport();

  const { displayStrategy, hasGraph } = useStableGraph(strategy);
  const activePlan = usePlanStore((s) => s.activePlan);
  const [planPanel, setPlanPanel] = useState<"closed" | "collapsed" | "open">("closed");

  // Auto-open plan panel when a plan is presented
  useEffect(() => {
    if (activePlan?.status === "presented") {
      setPlanPanel("open");
    }
  }, [activePlan?.status]);

  if (authLoading || configLoading) return <LoadingScreen />;
  if (setupRequired) return <SetupRequiredScreen onRetry={retryConfig} />;
  if (apiError !== null) return <ApiErrorScreen error={apiError} onRetry={retryAuth} />;

  return (
    <div className="flex h-full flex-col bg-background text-foreground">
      {!embedded && (
        <LoginModal
          open={!veupathdbSignedIn}
          selectedSite={selectedSite}
          onSiteChange={handleSiteChange}
        />
      )}
      <ToastContainer toasts={toasts} durationMs={durationMs} onDismiss={removeToast} />

      {embedded ? (
        <EmbeddedToolbar onOpenSettings={modals.openSettings} />
      ) : (
        <TopBar
          selectedSite={selectedSite}
          onSiteChange={handleSiteChange}
          actions={<TopBarActions onOpenSettings={modals.openSettings} />}
        />
      )}

      <div ref={layoutRef} className="flex min-h-0 flex-1 overflow-hidden">
        <div
          className="flex shrink-0 flex-col border-r border-border bg-sidebar"
          style={{ width: sidebarWidth }}
        >
          <ConversationSidebar siteId={selectedSite} onToast={addToast} />
        </div>

        <div
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize sidebar"
          onMouseDown={startDragging}
          className="w-1 cursor-col-resize bg-muted transition-colors duration-150 hover:bg-primary/20"
        />

        <div className="relative flex min-h-0 min-w-0 flex-1 flex-col bg-card">
          <div className="min-h-0 flex-1">
            <UnifiedChatPanel
              siteId={selectedSite}
              pendingAskNode={pendingAskNode}
              onConsumeAskNode={() => setPendingAskNode(null)}
            />
          </div>

          {hasGraph && displayStrategy && (
            <CompactStrategyView
              strategy={displayStrategy}
              onEditGraph={modals.openGraphEditor}
              onExportAsGeneSet={(s) => void handleExportAsGeneSet(s)}
              exportingGeneSet={exportingGeneSet}
            />
          )}

          <GraphEditorModal
            open={modals.graphEditing}
            onClose={modals.closeGraphEditor}
            strategy={displayStrategy ?? strategy}
            siteId={selectedSite}
            onToast={addToast}
          />
        </div>

        {/* Right panel: Strategy Plan */}
        {planPanel !== "closed" && activePlan != null && (
          <>
            <div className="w-px bg-border" />
            {planPanel === "collapsed" ? (
              <div className="flex h-full w-10 shrink-0 flex-col items-center border-l border-border bg-card pt-2 gap-2">
                <button
                  type="button"
                  onClick={() => setPlanPanel("open")}
                  className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
                  aria-label="Expand plan panel"
                  title="Expand plan"
                >
                  <ClipboardList className="h-5 w-5" />
                </button>
              </div>
            ) : (
              <div className="w-[380px] shrink-0">
                <PlanPanel
                  onClose={() => setPlanPanel("closed")}
                  onCollapse={() => setPlanPanel("collapsed")}
                />
              </div>
            )}
          </>
        )}
      </div>

      <SettingsPage
        open={modals.showSettings}
        onClose={modals.closeSettings}
        siteId={selectedSite}
      />
    </div>
  );
}

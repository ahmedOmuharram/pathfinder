"use client";

import { useState } from "react";
import { useSearchParams } from "next/navigation";
import { UnifiedChatPanel } from "@/features/chat/components/UnifiedChatPanel";
import { ConversationSidebar } from "@/features/sidebar/components/ConversationSidebar";
import { useShallow } from "zustand/react/shallow";
import { useSessionStore } from "@/state/useSessionStore";
import { useStrategyStore } from "@/state/strategy/store";

import { ToastContainer } from "@/app/components/ToastContainer";
import { LoginModal } from "@/app/components/LoginModal";
import { TopBar } from "@/app/components/TopBar";
import { TopBarActions } from "@/app/components/TopBarActions";
import { EmbeddedToolbar } from "@/app/components/EmbeddedToolbar";
import { GraphEditorModal } from "@/app/components/GraphEditorModal";
import { LoadingScreen } from "@/app/components/LoadingScreen";
import { QueryBoundary } from "@/lib/components/QueryBoundary";
import { AppShellError } from "@/app/components/AppShellError";
import { useToasts } from "@/app/hooks/useToasts";
import { useSidebarResize } from "@/app/hooks/useSidebarResize";
import { useModalState } from "@/app/hooks/useModalState";
import { useGeneSetExport } from "@/app/hooks/useGeneSetExport";
import { CompactStrategyView } from "@/features/strategy/graph/components/CompactStrategyView";
import { SettingsPage } from "@/features/settings/components/SettingsPage";
import { EngineModal } from "@/features/engine/components/EngineModal";
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
    <QueryBoundary
      loadingFallback={<LoadingScreen />}
      ErrorFallback={AppShellError}
    >
      <HomePageInner />
    </QueryBoundary>
  );
}

function HomePageInner() {
  const searchParams = useSearchParams();
  const embedded = searchParams.get("embedded") === "true";
  const siteIdParam = searchParams.get("siteId");

  const {
    selectedSite,
    strategyId,
    switchSite,
    veupathdbSignedIn,
    pendingAskNode,
    setPendingAskNode,
  } = useSessionStore(
    useShallow((s) => ({
      selectedSite: s.selectedSite,
      strategyId: s.strategyId,
      switchSite: s.switchSite,
      veupathdbSignedIn: s.veupathdbSignedIn,
      pendingAskNode: s.pendingAskNode,
      setPendingAskNode: s.setPendingAskNode,
    })),
  );
  useAuthCheck();
  const { setupRequired, retry: retryConfig } = useSystemConfig();
  useSiteTheme(selectedSite);
  useAuthRefresh();
  const strategy = useStrategyStore((s) => s.strategy);

  const { toasts, addToast, removeToast, durationMs } = useToasts();
  const { layoutRef, sidebarWidth, startDragging } = useSidebarResize();
  const modals = useModalState();

  const [prevSiteIdParam, setPrevSiteIdParam] = useState(siteIdParam);
  if (siteIdParam !== prevSiteIdParam) {
    setPrevSiteIdParam(siteIdParam);
    if (siteIdParam !== null && siteIdParam !== selectedSite) {
      switchSite(siteIdParam);
    }
  }

  const handleSiteChange = (nextSite: string) => switchSite(nextSite);

  // --- Workbench gene set export ---
  const { exportingGeneSet, handleExportAsGeneSet } = useGeneSetExport();

  const { displayStrategy, hasGraph } = useStableGraph(strategy);
  const activePlan = usePlanStore((s) => s.activePlan);
  const [planPanel, setPlanPanel] = useState<"closed" | "collapsed" | "open">("closed");
  const [prevPlanStatus, setPrevPlanStatus] = useState(activePlan?.status);
  if (activePlan?.status !== prevPlanStatus) {
    setPrevPlanStatus(activePlan?.status);
    if (activePlan?.status === "presented") setPlanPanel("open");
  }

  if (setupRequired) return <SetupRequiredScreen onRetry={retryConfig} />;

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
          actions={<TopBarActions onOpenSettings={modals.openSettings} onOpenEngine={modals.openEngine} />}
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
              key={strategyId ?? "none"}
              siteId={selectedSite}
              pendingAskNode={pendingAskNode}
              onConsumeAskNode={() => setPendingAskNode(null)}
              onOpenEngine={modals.openEngine}
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

      <EngineModal
        open={modals.showEngine}
        onClose={modals.closeEngine}
      />
    </div>
  );
}

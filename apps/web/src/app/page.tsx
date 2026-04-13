"use client";

import { useSearchParams } from "next/navigation";
import { ChatPanel } from "@/features/chat/ChatPanel";
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
import { setQueryErrorHandler } from "@/lib/query/client";
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
    selectedSite: storedSelectedSite,
    strategyId,
    switchSite,
    veupathdbSignedIn,
  } = useSessionStore(
    useShallow((s) => ({
      selectedSite: s.selectedSite,
      strategyId: s.strategyId,
      switchSite: s.switchSite,
      veupathdbSignedIn: s.veupathdbSignedIn,
    })),
  );
  const selectedSite = siteIdParam ?? storedSelectedSite;
  useAuthCheck();
  const { setupRequired, retry: retryConfig } = useSystemConfig();
  useSiteTheme(selectedSite);
  useAuthRefresh();
  const strategy = useStrategyStore((s) => s.strategy);

  const { toasts, addToast, removeToast, durationMs } = useToasts();
  setQueryErrorHandler((notice) =>
    addToast({ type: "error", message: notice.message }),
  );

  const { layoutRef, sidebarWidth, startDragging } = useSidebarResize();
  const modals = useModalState();

  const handleSiteChange = (nextSite: string) => switchSite(nextSite);

  // --- Workbench gene set export ---
  const { exportingGeneSet, handleExportAsGeneSet } = useGeneSetExport();

  const { displayStrategy, hasGraph } = useStableGraph(strategy);

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
            <ChatPanel chatId={strategyId ?? ""} mode="strategy" />
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

        {/* Plan artifacts now render inline in the chat via DataPlanArtifactPart → StrategyPlanCard. */}
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

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
import { LoginModal } from "@/app/components/LoginModal";
import { TopBar } from "@/app/components/TopBar";
import { Modal } from "@/lib/components/Modal";
import { Button } from "@/lib/components/ui/Button";
import { useToasts } from "@/app/hooks/useToasts";
import { useSidebarResize } from "@/app/hooks/useSidebarResize";
import { useBuildStrategy } from "@/features/strategy/hooks/useBuildStrategy";
import { FlaskConical, Loader2, MessageCircle, Settings, X } from "lucide-react";
import Link from "next/link";
import { CompactStrategyView } from "@/features/strategy/graph/components/CompactStrategyView";
import { SettingsPage } from "@/features/settings/components/SettingsPage";
import { useAuthCheck } from "@/app/hooks/useAuthCheck";
import { useSiteTheme } from "@/features/sites/hooks/useSiteTheme";

export default function HomePage() {
  const { selectedSite, setSelectedSite } = useSessionStore();
  const setStrategyId = useSessionStore((state) => state.setStrategyId);
  const setPlanSessionId = useSessionStore((state) => state.setPlanSessionId);
  const selectedSiteDisplayName = useSessionStore(
    (state) => state.selectedSiteDisplayName,
  );
  const veupathdbSignedIn = useSessionStore((state) => state.veupathdbSignedIn);
  const setAuthToken = useSessionStore((state) => state.setAuthToken);
  const { authLoading } = useAuthCheck();
  useSiteTheme(selectedSite);
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
      setPlanSessionId(null);
      clearStrategy();
    }
  }, [selectedSite, prevSite, setStrategyId, setPlanSessionId, clearStrategy]);

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

  if (authLoading) {
    return (
      <div className="flex h-full flex-col items-center justify-center bg-background text-foreground">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <p className="mt-3 text-sm text-muted-foreground">Loading…</p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col bg-background text-foreground">
      <LoginModal
        open={!veupathdbSignedIn}
        selectedSite={selectedSite}
        onSiteChange={handleSiteChange}
      />
      <ToastContainer toasts={toasts} durationMs={durationMs} onDismiss={removeToast} />

      <TopBar
        selectedSite={selectedSite}
        onSiteChange={handleSiteChange}
        actions={
          <div className="flex items-center gap-1">
            <Button
              size="sm"
              className="pointer-events-none bg-primary/10 text-primary shadow-none"
            >
              <MessageCircle className="h-3.5 w-3.5" aria-hidden />
              Chat
            </Button>
            <Link
              href="/experiments"
              className="inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium text-muted-foreground transition-all duration-150 hover:bg-accent hover:text-accent-foreground"
            >
              <FlaskConical className="h-3.5 w-3.5" aria-hidden />
              Experiments
            </Link>
            <div className="mx-1 h-5 w-px bg-border" />
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setShowSettings(true)}
              aria-label="Settings"
            >
              <Settings className="h-4 w-4" aria-hidden />
            </Button>
          </div>
        }
      />

      <div ref={layoutRef} className="flex min-h-0 flex-1 overflow-hidden">
        <div
          className="flex shrink-0 flex-col border-r border-border bg-sidebar"
          style={{ width: sidebarWidth }}
        >
          <ConversationSidebar siteId={selectedSite} onToast={addToast} />
        </div>

        <div
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

          {hasGraph && (
            <CompactStrategyView
              strategy={strategy}
              onEditGraph={() => setGraphEditing(true)}
            />
          )}

          <Modal
            open={graphEditing}
            onClose={() => setGraphEditing(false)}
            title="Graph Editor"
            maxWidth="max-w-[95vw]"
          >
            <div className="flex h-[90vh] flex-col overflow-hidden rounded-lg">
              <div className="flex items-center justify-between border-b border-border bg-muted/50 px-4 py-2.5">
                <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Graph Editor
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setGraphEditing(false)}
                >
                  <X className="h-3.5 w-3.5" aria-hidden />
                  Close
                </Button>
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

      <Modal
        open={!!pendingSiteChange}
        onClose={() => setPendingSiteChange(null)}
        title="Switch site?"
        maxWidth="max-w-sm"
      >
        <div className="px-5 pb-5 pt-2">
          <p className="text-sm text-muted-foreground">
            Your current strategy will be cleared when you switch sites. Are you sure
            you want to continue?
          </p>
          <div className="mt-4 flex justify-end gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPendingSiteChange(null)}
            >
              Cancel
            </Button>
            <Button size="sm" onClick={confirmSiteChange}>
              Switch site
            </Button>
          </div>
        </div>
      </Modal>

      <SettingsPage
        open={showSettings}
        onClose={() => setShowSettings(false)}
        siteId={selectedSite}
      />
    </div>
  );
}

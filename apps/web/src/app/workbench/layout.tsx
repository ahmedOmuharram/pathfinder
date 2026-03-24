"use client";

import { type ReactNode, useCallback, useEffect, useRef, useState } from "react";
import { useSessionStore } from "@/state/useSessionStore";
import { TopBar } from "@/app/components/TopBar";
import { LoginModal } from "@/app/components/LoginModal";
import { SettingsPage } from "@/features/settings/components/SettingsPage";
import { useAuthCheck } from "@/app/hooks/useAuthCheck";
import { useAuthRefresh } from "@/app/hooks/useAuthRefresh";
import { useSystemConfig } from "@/app/hooks/useSystemConfig";
import { SetupRequiredScreen } from "@/app/components/SetupRequiredScreen";
import { useSiteTheme } from "@/features/sites/hooks/useSiteTheme";
import { WorkbenchSidebar } from "@/features/workbench/components/WorkbenchSidebar";
import { GeneSearchSidebar } from "@/features/workbench/components/GeneSearchSidebar";
import { SidebarEdgeTab } from "@/features/workbench/components/SidebarEdgeTab";
import { listGeneSets } from "@/features/workbench/api/geneSets";
import { useWorkbenchStore } from "@/state/useWorkbenchStore";
import { Button } from "@/lib/components/ui/Button";
import {
  AlertTriangle,
  Layers,
  List,
  Loader2,
  MessageCircle,
  RefreshCw,
  Search,
  Settings,
} from "lucide-react";
import Link from "next/link";

export default function WorkbenchLayout({ children }: { children: ReactNode }) {
  const { selectedSite, setSelectedSite } = useSessionStore();
  const veupathdbSignedIn = useSessionStore((s) => s.veupathdbSignedIn);
  const { authLoading, apiError, retry: retryAuth } = useAuthCheck();
  const { configLoading, setupRequired, retry: retryConfig } = useSystemConfig();
  useSiteTheme(selectedSite);
  useAuthRefresh();

  const handleSiteChange = useCallback(
    (nextSite: string) => setSelectedSite(nextSite),
    [setSelectedSite],
  );

  const [showSettings, setShowSettings] = useState(false);
  const geneSearchOpen = useWorkbenchStore((s) => s.geneSearchOpen);
  const toggleGeneSearch = useWorkbenchStore((s) => s.toggleGeneSearch);
  const leftSidebarOpen = useWorkbenchStore((s) => s.leftSidebarOpen);
  const toggleLeftSidebar = useWorkbenchStore((s) => s.toggleLeftSidebar);

  // Load gene sets from API on mount / site change.
  // Uses mergeGeneSets (not addGeneSet) so the layout never auto-activates —
  // activation is the page's responsibility (/workbench = none, /workbench/[id] = id).
  const mergeGeneSets = useWorkbenchStore((s) => s.mergeGeneSets);
  const resetWorkbench = useWorkbenchStore((s) => s.reset);
  const prevSiteRef = useRef(selectedSite);
  useEffect(() => {
    if (!veupathdbSignedIn || authLoading) return;
    if (prevSiteRef.current !== selectedSite) {
      resetWorkbench();
      prevSiteRef.current = selectedSite;
    }
    listGeneSets(selectedSite)
      .then((sets) => {
        mergeGeneSets(sets);
      })
      .catch((err) => {
        console.error("[loadGeneSets]", err);
      });
  }, [selectedSite, veupathdbSignedIn, authLoading, resetWorkbench, mergeGeneSets]);

  if (authLoading || configLoading) {
    return (
      <div className="flex h-full flex-col items-center justify-center bg-background text-foreground">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <p className="mt-3 text-sm text-muted-foreground">Loading...</p>
      </div>
    );
  }

  if (setupRequired) return <SetupRequiredScreen onRetry={retryConfig} />;

  if (apiError !== null) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 bg-background text-foreground">
        <AlertTriangle className="h-10 w-10 text-destructive" />
        <div className="text-center">
          <p className="text-sm font-medium">Unable to connect to the API</p>
          <p className="mt-1 max-w-sm text-xs text-muted-foreground">{apiError}</p>
        </div>
        <Button variant="outline" size="sm" onClick={retryAuth}>
          <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
          Retry
        </Button>
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
      <TopBar
        selectedSite={selectedSite}
        onSiteChange={handleSiteChange}
        actions={
          <div className="flex items-center gap-1">
            <Link
              href="/"
              className="inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium text-muted-foreground transition-all duration-150 hover:bg-accent hover:text-accent-foreground"
            >
              <MessageCircle className="h-3.5 w-3.5" />
              Chat
            </Link>
            <span
              className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground"
              aria-current="page"
            >
              <Layers className="h-3.5 w-3.5" aria-hidden />
              Workbench
            </span>
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

      <div className="flex min-h-0 flex-1 overflow-hidden">
        {leftSidebarOpen ? (
          <div className="w-96 shrink-0 border-r border-border bg-sidebar">
            <WorkbenchSidebar onCollapse={toggleLeftSidebar} />
          </div>
        ) : (
          <SidebarEdgeTab
            side="left"
            label="Gene Sets"
            icon={<List className="h-4 w-4" />}
            onClick={toggleLeftSidebar}
          />
        )}

        <div className="min-h-0 min-w-0 flex-1 overflow-y-auto bg-card">{children}</div>

        {geneSearchOpen ? (
          <div className="w-80 shrink-0 border-l border-border bg-sidebar">
            <GeneSearchSidebar onCollapse={toggleGeneSearch} />
          </div>
        ) : (
          <SidebarEdgeTab
            side="right"
            label="Gene Search"
            icon={<Search className="h-4 w-4" />}
            onClick={toggleGeneSearch}
          />
        )}
      </div>

      <SettingsPage
        open={showSettings}
        onClose={() => setShowSettings(false)}
        siteId={selectedSite}
      />
    </div>
  );
}

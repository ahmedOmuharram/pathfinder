"use client";

import { type ReactNode, useState } from "react";
import { useSuspenseQuery } from "@tanstack/react-query";
import { useShallow } from "zustand/react/shallow";
import { useSessionStore } from "@/state/useSessionStore";
import { TopBar } from "@/app/components/TopBar";
import { LoginModal } from "@/app/components/LoginModal";
import { LoadingScreen } from "@/app/components/LoadingScreen";
import { SettingsPage } from "@/features/settings/components/SettingsPage";
import { useAuthRefresh } from "@/lib/query/hooks/useAuthRefresh";
import { useSystemConfig } from "@/app/hooks/useSystemConfig";
import { SetupRequiredScreen } from "@/app/components/SetupRequiredScreen";
import { useSiteTheme } from "@/features/sites/hooks/useSiteTheme";
import { WorkbenchSidebar } from "@/features/workbench/components/WorkbenchSidebar";
import { GeneSearchSidebar } from "@/features/workbench/components/GeneSearchSidebar";
import { SidebarEdgeTab } from "@/features/workbench/components/SidebarEdgeTab";
import { useWorkbenchStore } from "@/state/useWorkbenchStore";
import { authStatusOptions } from "@/lib/api/veupathdb-auth";
import { QueryBoundary } from "@/lib/components/QueryBoundary";
import { AppShellError } from "@/app/components/AppShellError";
import { Button } from "@/lib/components/ui/Button";
import {
  Layers,
  List,
  MessageCircle,
  Search,
  Settings,
} from "lucide-react";
import Link from "next/link";

export default function WorkbenchLayout({ children }: { children: ReactNode }) {
  return (
    <QueryBoundary
      loadingFallback={<LoadingScreen />}
      ErrorFallback={AppShellError}
    >
      <WorkbenchLayoutInner>{children}</WorkbenchLayoutInner>
    </QueryBoundary>
  );
}

function WorkbenchLayoutInner({ children }: { children: ReactNode }) {
  const { selectedSite, switchSite } = useSessionStore(
    useShallow((s) => ({
      selectedSite: s.selectedSite,
      switchSite: s.switchSite,
    })),
  );
  const { data: authStatus } = useSuspenseQuery(authStatusOptions(selectedSite));
  const veupathdbSignedIn = authStatus.signedIn;
  const { setupRequired, retry: retryConfig } = useSystemConfig();
  useSiteTheme(selectedSite);
  useAuthRefresh();

  const handleSiteChange = (nextSite: string) => switchSite(nextSite);

  const [showSettings, setShowSettings] = useState(false);
  const {
    geneSearchOpen,
    toggleGeneSearch,
    leftSidebarOpen,
    toggleLeftSidebar,
  } = useWorkbenchStore(
    useShallow((s) => ({
      geneSearchOpen: s.geneSearchOpen,
      toggleGeneSearch: s.toggleGeneSearch,
      leftSidebarOpen: s.leftSidebarOpen,
      toggleLeftSidebar: s.toggleLeftSidebar,
    })),
  );

  if (setupRequired) return <SetupRequiredScreen onRetry={retryConfig} />;

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

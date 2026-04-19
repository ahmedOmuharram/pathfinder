"use client";

import { type ReactNode, use, useState } from "react";
import { useRouter } from "next/navigation";
import { useSuspenseQuery } from "@tanstack/react-query";
import { useShallow } from "zustand/react/shallow";
import { useSessionStore } from "@/state/useSessionStore";
import { AppNavRail } from "@/app/components/AppNavRail";
import { TopBar } from "@/app/components/TopBar";
import { LoginModal } from "@/app/components/LoginModal";
import { LoadingScreen } from "@/app/components/LoadingScreen";
import { SettingsPage } from "@/features/settings/components/SettingsPage";
import { EngineModal } from "@/features/engine/components/EngineModal";
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
import { Search } from "lucide-react";

export default function WorkbenchLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ siteId: string }>;
}) {
  const { siteId } = use(params);
  return (
    <QueryBoundary
      loadingFallback={<LoadingScreen />}
      ErrorFallback={AppShellError}
    >
      <WorkbenchLayoutInner siteId={siteId}>{children}</WorkbenchLayoutInner>
    </QueryBoundary>
  );
}

function WorkbenchLayoutInner({
  siteId,
  children,
}: {
  siteId: string;
  children: ReactNode;
}) {
  const router = useRouter();
  const storedSite = useSessionStore((s) => s.selectedSite);
  const selectedSite = siteId;

  if (storedSite !== siteId) {
    useSessionStore.setState({ selectedSite: siteId });
  }
  const { data: authStatus } = useSuspenseQuery(authStatusOptions(selectedSite));
  const veupathdbSignedIn = authStatus.signedIn;
  const { setupRequired, retry: retryConfig } = useSystemConfig();
  useSiteTheme(selectedSite);
  useAuthRefresh();

  const handleSiteChange = (nextSite: string) => {
    router.push(`/${nextSite}/workbench`);
  };

  const [showSettings, setShowSettings] = useState(false);
  const [showEngine, setShowEngine] = useState(false);
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
      <TopBar selectedSite={selectedSite} />

      <div className="flex min-h-0 flex-1 overflow-hidden">
        <AppNavRail
          siteId={selectedSite}
          onSiteChange={handleSiteChange}
          onOpenSettings={() => setShowSettings(true)}
          onOpenEngine={() => setShowEngine(true)}
          onToggleSidebar={toggleLeftSidebar}
          sidebarExpanded={leftSidebarOpen}
        />
        {leftSidebarOpen && (
          <div className="w-96 shrink-0 border-r border-border bg-sidebar">
            <WorkbenchSidebar onCollapse={toggleLeftSidebar} />
          </div>
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

      <EngineModal open={showEngine} onClose={() => setShowEngine(false)} />
    </div>
  );
}

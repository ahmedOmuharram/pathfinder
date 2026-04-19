"use client";

import { use } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useSuspenseQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";

import { toast } from "sonner";

import { AppNavRail } from "@/app/components/AppNavRail";
import { AppShellError } from "@/app/components/AppShellError";
import { EmbeddedToolbar } from "@/app/components/EmbeddedToolbar";
import { LoadingScreen } from "@/app/components/LoadingScreen";
import { LoginModal } from "@/app/components/LoginModal";
import { SetupRequiredScreen } from "@/app/components/SetupRequiredScreen";
import { TopBar } from "@/app/components/TopBar";
import { useAuthRefresh } from "@/lib/query/hooks/useAuthRefresh";
import { useAutoCollapseSidebar } from "@/app/hooks/useAutoCollapseSidebar";
import { useModalState } from "@/app/hooks/useModalState";
import { useSidebarResize } from "@/app/hooks/useSidebarResize";
import { useSystemConfig } from "@/app/hooks/useSystemConfig";
import { EngineModal } from "@/features/engine/components/EngineModal";
import { SettingsPage } from "@/features/settings/components/SettingsPage";
import { ConversationSidebar } from "@/features/sidebar/components/ConversationSidebar";
import { useSiteTheme } from "@/features/sites/hooks/useSiteTheme";
import { authStatusOptions } from "@/lib/api/veupathdb-auth";
import { QueryBoundary } from "@/lib/components/QueryBoundary";
import { setQueryErrorHandler } from "@/lib/query/client";
import { useLeftSidebarStore } from "@/state/useRightRailStore";
import { useSessionStore } from "@/state/useSessionStore";

export default function AppShellLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ siteId: string }>;
}) {
  const { siteId } = use(params);
  return (
    <QueryBoundary
      loadingFallback={<LoadingScreen />}
      ErrorFallback={AppShellError}
    >
      <AppShellInner siteId={siteId}>{children}</AppShellInner>
    </QueryBoundary>
  );
}

function AppShellInner({
  siteId,
  children,
}: {
  siteId: string;
  children: React.ReactNode;
}) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const embedded = searchParams.get("embedded") === "true";

  const storedSite = useSessionStore((s) => s.selectedSite);
  const selectedSite = siteId;

  // URL is the source of truth; keep the session store in sync so
  // downstream consumers that still read from it see the current site.
  if (storedSite !== siteId) {
    useSessionStore.setState({ selectedSite: siteId });
  }

  const { data: authStatus } = useSuspenseQuery(authStatusOptions(selectedSite));
  const veupathdbSignedIn = authStatus.signedIn;
  useAuthRefresh();
  useSiteTheme(selectedSite);
  const { setupRequired, retry: retryConfig } = useSystemConfig();

  setQueryErrorHandler((notice) => {
    toast.error(notice.message);
  });

  const { layoutRef, sidebarWidth, isDragging, startDragging } = useSidebarResize();
  const leftCollapsed = useLeftSidebarStore((s) => s.collapsed);
  const toggleLeft = useLeftSidebarStore((s) => s.toggle);
  useAutoCollapseSidebar();
  const modals = useModalState();

  const handleSiteChange = (nextSite: string) => {
    router.push(`/${nextSite}/conversation`);
  };

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
      {embedded ? (
        <EmbeddedToolbar
          siteId={selectedSite}
          onOpenSettings={modals.openSettings}
        />
      ) : (
        <TopBar selectedSite={selectedSite} />
      )}

      <div ref={layoutRef} className="flex min-h-0 flex-1 overflow-hidden">
        {!embedded && (
          <AppNavRail
            siteId={selectedSite}
            onSiteChange={handleSiteChange}
            onOpenSettings={modals.openSettings}
            onOpenEngine={modals.openEngine}
            onToggleSidebar={toggleLeft}
            sidebarExpanded={!leftCollapsed}
          />
        )}

        <AnimatePresence initial={false}>
          {!leftCollapsed && (
            <motion.div
              key="sidebar-expanded"
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: sidebarWidth, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={
                isDragging
                  ? { duration: 0 }
                  : { type: "spring", stiffness: 380, damping: 36 }
              }
              className="h-full shrink-0 overflow-hidden border-r border-border bg-sidebar"
            >
              <div style={{ width: sidebarWidth }} className="h-full">
                <ConversationSidebar siteId={selectedSite} />
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {!leftCollapsed && (
          <div
            role="separator"
            aria-orientation="vertical"
            aria-label="Resize sidebar"
            onMouseDown={startDragging}
            className="w-1 cursor-col-resize bg-muted transition-colors duration-150 hover:bg-primary/20"
          />
        )}

        <div className="flex min-h-0 min-w-0 flex-1 flex-col">{children}</div>
      </div>

      <SettingsPage
        open={modals.showSettings}
        onClose={modals.closeSettings}
        siteId={selectedSite}
      />

      <EngineModal open={modals.showEngine} onClose={modals.closeEngine} />
    </div>
  );
}

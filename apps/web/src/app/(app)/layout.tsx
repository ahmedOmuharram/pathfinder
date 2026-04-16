"use client";

import { useSearchParams } from "next/navigation";
import { useShallow } from "zustand/react/shallow";

import { toast } from "sonner";

import { AppShellError } from "@/app/components/AppShellError";
import { EmbeddedToolbar } from "@/app/components/EmbeddedToolbar";
import { LoadingScreen } from "@/app/components/LoadingScreen";
import { LoginModal } from "@/app/components/LoginModal";
import { SetupRequiredScreen } from "@/app/components/SetupRequiredScreen";
import { TopBar } from "@/app/components/TopBar";
import { TopBarActions } from "@/app/components/TopBarActions";
import { useAuthCheck } from "@/app/hooks/useAuthCheck";
import { useAuthRefresh } from "@/app/hooks/useAuthRefresh";
import { useModalState } from "@/app/hooks/useModalState";
import { useSidebarResize } from "@/app/hooks/useSidebarResize";
import { useSystemConfig } from "@/app/hooks/useSystemConfig";
import { EngineModal } from "@/features/engine/components/EngineModal";
import { SettingsPage } from "@/features/settings/components/SettingsPage";
import { ConversationSidebar } from "@/features/sidebar/components/ConversationSidebar";
import { useSiteTheme } from "@/features/sites/hooks/useSiteTheme";
import { QueryBoundary } from "@/lib/components/QueryBoundary";
import { setQueryErrorHandler } from "@/lib/query/client";
import { useSessionStore } from "@/state/useSessionStore";

export default function AppShellLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <QueryBoundary
      loadingFallback={<LoadingScreen />}
      ErrorFallback={AppShellError}
    >
      <AppShellInner>{children}</AppShellInner>
    </QueryBoundary>
  );
}

function AppShellInner({ children }: { children: React.ReactNode }) {
  const searchParams = useSearchParams();
  const embedded = searchParams.get("embedded") === "true";
  const siteIdParam = searchParams.get("siteId");

  const { selectedSite: storedSelectedSite, switchSite, veupathdbSignedIn } =
    useSessionStore(
      useShallow((s) => ({
        selectedSite: s.selectedSite,
        switchSite: s.switchSite,
        veupathdbSignedIn: s.veupathdbSignedIn,
      })),
    );
  const selectedSite = siteIdParam ?? storedSelectedSite;

  useAuthCheck();
  useAuthRefresh();
  useSiteTheme(selectedSite);
  const { setupRequired, retry: retryConfig } = useSystemConfig();

  setQueryErrorHandler((notice) => {
    toast.error(notice.message);
  });

  const { layoutRef, sidebarWidth, startDragging } = useSidebarResize();
  const modals = useModalState();

  const handleSiteChange = (nextSite: string) => switchSite(nextSite);

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
        <EmbeddedToolbar onOpenSettings={modals.openSettings} />
      ) : (
        <TopBar
          selectedSite={selectedSite}
          onSiteChange={handleSiteChange}
          actions={
            <TopBarActions
              onOpenSettings={modals.openSettings}
              onOpenEngine={modals.openEngine}
            />
          }
        />
      )}

      <div ref={layoutRef} className="flex min-h-0 flex-1 overflow-hidden">
        <div
          className="flex shrink-0 flex-col border-r border-border bg-sidebar"
          style={{ width: sidebarWidth }}
        >
          <ConversationSidebar siteId={selectedSite} />
        </div>

        <div
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize sidebar"
          onMouseDown={startDragging}
          className="w-1 cursor-col-resize bg-muted transition-colors duration-150 hover:bg-primary/20"
        />

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

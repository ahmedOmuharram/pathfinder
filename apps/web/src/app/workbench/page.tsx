"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useSessionStore } from "@/state/useSessionStore";
import { TopBar } from "@/app/components/TopBar";
import { LoginModal } from "@/app/components/LoginModal";
import { SettingsPage } from "@/features/settings/components/SettingsPage";
import { useAuthCheck } from "@/app/hooks/useAuthCheck";
import { refreshAuth } from "@/lib/api/client";
import { useSiteTheme } from "@/features/sites/hooks/useSiteTheme";
import { WorkbenchSidebar } from "@/features/workbench/components/WorkbenchSidebar";
import { WorkbenchMain } from "@/features/workbench/components/WorkbenchMain";
import { GeneSearchSidebar } from "@/features/workbench/components/GeneSearchSidebar";
import { listGeneSets } from "@/features/workbench/api/geneSets";
import { useWorkbenchStore } from "@/features/workbench/store";
import { Button } from "@/lib/components/ui/Button";
import {
  AlertTriangle,
  Layers,
  Loader2,
  MessageCircle,
  RefreshCw,
  Search,
  Settings,
} from "lucide-react";
import Link from "next/link";

export default function WorkbenchPage() {
  const { selectedSite, setSelectedSite } = useSessionStore();
  const veupathdbSignedIn = useSessionStore((s) => s.veupathdbSignedIn);
  const { authLoading, apiError, retry: retryAuth } = useAuthCheck();
  useSiteTheme(selectedSite);
  const authRefreshed = useSessionStore((s) => s.authRefreshed);
  const setAuthRefreshed = useSessionStore((s) => s.setAuthRefreshed);

  const handleSiteChange = useCallback(
    (nextSite: string) => {
      setSelectedSite(nextSite);
    },
    [setSelectedSite],
  );

  const bumpAuthVersion = useSessionStore((s) => s.bumpAuthVersion);
  useEffect(() => {
    if (!veupathdbSignedIn || authRefreshed) return;
    setAuthRefreshed(true);
    refreshAuth()
      .then(() => bumpAuthVersion())
      .catch((err) => {
        console.error("[refreshAuth]", err);
      });
  }, [veupathdbSignedIn, authRefreshed, setAuthRefreshed, bumpAuthVersion]);

  const [showSettings, setShowSettings] = useState(false);
  const geneSearchOpen = useWorkbenchStore((s) => s.geneSearchOpen);
  const toggleGeneSearch = useWorkbenchStore((s) => s.toggleGeneSearch);

  // Load gene sets from API on mount / site change
  const addGeneSet = useWorkbenchStore((s) => s.addGeneSet);
  const resetWorkbench = useWorkbenchStore((s) => s.reset);
  const prevSiteRef = useRef(selectedSite);
  useEffect(() => {
    if (!veupathdbSignedIn || authLoading) return;
    // Clear stale gene sets when switching sites
    if (prevSiteRef.current !== selectedSite) {
      resetWorkbench();
      prevSiteRef.current = selectedSite;
    }
    listGeneSets(selectedSite)
      .then((sets) => {
        const existingIds = new Set(
          useWorkbenchStore.getState().geneSets.map((gs) => gs.id),
        );
        for (const gs of sets) {
          if (!existingIds.has(gs.id)) {
            addGeneSet(gs);
          }
        }
      })
      .catch((err) => {
        console.error("[loadGeneSets]", err);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedSite, veupathdbSignedIn, authLoading]);

  if (authLoading) {
    return (
      <div className="flex h-full flex-col items-center justify-center bg-background text-foreground">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <p className="mt-3 text-sm text-muted-foreground">Loading...</p>
      </div>
    );
  }

  if (apiError) {
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
              onClick={toggleGeneSearch}
              aria-label="Toggle gene search"
              aria-pressed={geneSearchOpen}
              className={geneSearchOpen ? "bg-white/20" : ""}
            >
              <Search className="h-4 w-4" aria-hidden />
            </Button>
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
        <div className="w-64 shrink-0 border-r border-border bg-sidebar">
          <WorkbenchSidebar />
        </div>

        <div className="min-h-0 min-w-0 flex-1 bg-card">
          <WorkbenchMain />
        </div>

        {geneSearchOpen && (
          <div className="w-80 shrink-0 border-l border-border bg-sidebar">
            <GeneSearchSidebar />
          </div>
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

"use client";

import { useCallback, useEffect, useState } from "react";
import { useSessionStore } from "@/state/useSessionStore";
import { TopBar } from "@/app/components/TopBar";
import { LoginModal } from "@/app/components/LoginModal";
import { SettingsPage } from "@/features/settings/components/SettingsPage";
import { useAuthCheck } from "@/app/hooks/useAuthCheck";
import { refreshAuth } from "@/lib/api/client";
import { useSiteTheme } from "@/features/sites/hooks/useSiteTheme";
import { useExperimentStore } from "@/features/experiments/store";
import { ExperimentList } from "@/features/experiments/components/ExperimentList";
import { ModeChooser } from "@/features/experiments/components/ModeChooser";
import { SetupWizard } from "@/features/experiments/components/SetupWizard";
import { MultiStepBuilder } from "@/features/experiments/components/MultiStepBuilder";
import { ResultsDashboard } from "@/features/experiments/components/ResultsDashboard";
import { CompareView } from "@/features/experiments/components/CompareView";
import { OverlapView } from "@/features/experiments/components/OverlapView";
import { EnrichmentCompareView } from "@/features/experiments/components/EnrichmentCompareView";
import { RunningPanel } from "@/features/experiments/components/RunningPanel";
import { EmptyState } from "@/lib/components/ui/EmptyState";
import { Button } from "@/lib/components/ui/Button";
import { FlaskConical, Loader2, MessageCircle, Settings } from "lucide-react";
import Link from "next/link";

export default function ExperimentsPage() {
  const { selectedSite, setSelectedSite } = useSessionStore();
  const veupathdbSignedIn = useSessionStore((s) => s.veupathdbSignedIn);
  const setAuthToken = useSessionStore((s) => s.setAuthToken);
  const { authLoading } = useAuthCheck();
  useSiteTheme(selectedSite);
  const authRefreshed = useSessionStore((s) => s.authRefreshed);
  const setAuthRefreshed = useSessionStore((s) => s.setAuthRefreshed);

  const { view, currentExperiment, compareExperiment, isRunning, experiments } =
    useExperimentStore();

  const handleSiteChange = useCallback(
    (nextSite: string) => {
      setSelectedSite(nextSite);
    },
    [setSelectedSite],
  );

  useEffect(() => {
    if (!veupathdbSignedIn || authRefreshed) return;
    setAuthRefreshed(true);
    refreshAuth()
      .then((result) => {
        if (result.authToken) setAuthToken(result.authToken);
      })
      .catch(() => setAuthToken(null));
  }, [veupathdbSignedIn, authRefreshed, setAuthRefreshed, setAuthToken]);

  const { setView } = useExperimentStore.getState();
  const [showSettings, setShowSettings] = useState(false);

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
            <Button
              size="sm"
              className="pointer-events-none bg-primary/10 text-primary shadow-none"
            >
              <FlaskConical className="h-3.5 w-3.5" />
              Experiments
            </Button>
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
        <div className="w-64 shrink-0 border-r border-border bg-sidebar">
          <ExperimentList siteId={selectedSite} />
        </div>

        <div className="min-h-0 min-w-0 flex-1 bg-card">
          {isRunning ? (
            <RunningPanel />
          ) : view === "mode-select" ? (
            <ModeChooser />
          ) : view === "setup" ? (
            <SetupWizard siteId={selectedSite} />
          ) : view === "multi-step-setup" ? (
            <MultiStepBuilder siteId={selectedSite} />
          ) : view === "results" && currentExperiment ? (
            <ResultsDashboard experiment={currentExperiment} siteId={selectedSite} />
          ) : view === "compare" && currentExperiment && compareExperiment ? (
            <CompareView
              experimentA={currentExperiment}
              experimentB={compareExperiment}
            />
          ) : view === "overlap" ? (
            <OverlapView experiments={experiments} />
          ) : view === "enrichment-compare" ? (
            <EnrichmentCompareView experiments={experiments} />
          ) : (
            <EmptyState
              icon={<FlaskConical className="h-10 w-10" />}
              heading="Experiment Lab"
              description="Evaluate search performance with ML metrics, cross-validation, and enrichment analysis."
              action={
                <Button onClick={() => setView("mode-select")}>New Experiment</Button>
              }
            />
          )}
        </div>
      </div>

      <SettingsPage
        open={showSettings}
        onClose={() => setShowSettings(false)}
        siteId={selectedSite}
      />
    </div>
  );
}

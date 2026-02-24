"use client";

import { useCallback, useEffect } from "react";
import { useSessionStore } from "@/state/useSessionStore";
import { TopBar } from "@/app/components/TopBar";
import { LoginGate } from "@/app/components/LoginGate";
import { refreshAuth } from "@/lib/api/client";
import { useExperimentStore } from "@/features/experiments/store";
import { ExperimentList } from "@/features/experiments/components/ExperimentList";
import { SetupWizard } from "@/features/experiments/components/SetupWizard";
import { ResultsDashboard } from "@/features/experiments/components/ResultsDashboard";
import { CompareView } from "@/features/experiments/components/CompareView";
import { OverlapView } from "@/features/experiments/components/OverlapView";
import { EnrichmentCompareView } from "@/features/experiments/components/EnrichmentCompareView";
import { RunningPanel } from "@/features/experiments/components/RunningPanel";
import { EmptyState } from "@/lib/components/ui/EmptyState";
import { Button } from "@/lib/components/ui/Button";
import { FlaskConical, MessageCircle } from "lucide-react";
import Link from "next/link";

export default function ExperimentsPage() {
  const { selectedSite, setSelectedSite } = useSessionStore();
  const veupathdbSignedIn = useSessionStore((s) => s.veupathdbSignedIn);
  const setAuthToken = useSessionStore((s) => s.setAuthToken);
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

  if (!veupathdbSignedIn) {
    return <LoginGate selectedSite={selectedSite} onSiteChange={handleSiteChange} />;
  }

  const { setView } = useExperimentStore.getState();

  return (
    <div className="flex h-full flex-col bg-background text-foreground">
      <TopBar
        selectedSite={selectedSite}
        onSiteChange={handleSiteChange}
        actions={
          <div className="flex items-center gap-2">
            <Link
              href="/"
              className="inline-flex items-center gap-1.5 rounded-md border border-input bg-background px-3 py-1.5 text-xs font-medium shadow-xs transition-all duration-150 hover:bg-accent hover:text-accent-foreground hover:-translate-y-px active:translate-y-0"
            >
              <MessageCircle className="h-3.5 w-3.5" />
              Chat
            </Link>
            <Button size="sm" className="pointer-events-none">
              <FlaskConical className="h-3.5 w-3.5" />
              Experiments
            </Button>
          </div>
        }
      />

      <div className="flex min-h-0 flex-1 overflow-hidden">
        <div className="w-64 shrink-0 border-r border-border bg-card">
          <ExperimentList siteId={selectedSite} />
        </div>

        <div className="min-h-0 min-w-0 flex-1 bg-card">
          {isRunning ? (
            <RunningPanel />
          ) : view === "setup" ? (
            <SetupWizard siteId={selectedSite} />
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
              action={<Button onClick={() => setView("setup")}>New Experiment</Button>}
            />
          )}
        </div>
      </div>
    </div>
  );
}

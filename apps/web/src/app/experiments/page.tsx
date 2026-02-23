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

  return (
    <div className="flex h-full flex-col bg-slate-50 text-slate-900">
      <TopBar
        selectedSite={selectedSite}
        onSiteChange={handleSiteChange}
        actions={
          <div className="flex items-center gap-2">
            <Link
              href="/"
              className="flex items-center gap-1.5 rounded-md border border-slate-200 px-3 py-1.5 text-[11px] font-medium text-slate-600 transition hover:bg-slate-50"
            >
              <MessageCircle className="h-3.5 w-3.5" />
              Chat
            </Link>
            <div className="flex items-center gap-1.5 rounded-md bg-slate-900 px-3 py-1.5 text-[11px] font-medium text-white">
              <FlaskConical className="h-3.5 w-3.5" />
              Experiments
            </div>
          </div>
        }
      />

      <div className="flex min-h-0 flex-1 overflow-hidden">
        {/* Sidebar: experiment list */}
        <div className="w-64 shrink-0 border-r border-slate-200 bg-white">
          <ExperimentList siteId={selectedSite} />
        </div>

        {/* Main content area */}
        <div className="min-h-0 min-w-0 flex-1 bg-white">
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
            <EmptyState />
          )}
        </div>
      </div>
    </div>
  );
}

function EmptyState() {
  const { setView } = useExperimentStore();

  return (
    <div className="flex h-full items-center justify-center">
      <div className="text-center">
        <FlaskConical className="mx-auto h-12 w-12 text-slate-300" />
        <h2 className="mt-3 text-base font-semibold text-slate-700">Experiment Lab</h2>
        <p className="mt-1 max-w-sm text-[12px] text-slate-500">
          Evaluate VEuPathDB searches with ML metrics, cross-validation, and enrichment
          analysis. No AI required -- configure and run experiments directly.
        </p>
        <button
          type="button"
          onClick={() => setView("setup")}
          className="mt-4 rounded-md bg-slate-900 px-4 py-2 text-[12px] font-medium text-white transition hover:bg-slate-800"
        >
          Create your first experiment
        </button>
      </div>
    </div>
  );
}

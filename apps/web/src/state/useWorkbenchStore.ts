/**
 * Workbench state store — manages gene-set selection and analysis panel UI state.
 *
 * Gene-set data itself lives in TanStack Query (useGeneSetsQuery).
 * This store only tracks selection/activation IDs and UI controls.
 */

import { create } from "zustand";
import type { Experiment } from "@pathfinder/shared";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type PanelId =
  | "enrichment"
  | "distributions"
  | "evaluate"
  | "sweep"
  | "batch"
  | "results-table"
  | "step-analysis"
  | "ai-insights"
  | "custom-enrichment"
  | "ensemble"
  | "confidence"
  | "benchmark"
  | "reverse-search";

// ---------------------------------------------------------------------------
// Store shape
// ---------------------------------------------------------------------------

interface WorkbenchState {
  activeSetId: string | null;
  selectedSetIds: string[];
  expandedPanels: Set<PanelId>;
  lastExperiment: Experiment | null;
  lastExperimentSetId: string | null;
  geneSearchOpen: boolean;
  leftSidebarOpen: boolean;

  // Actions — gene set selection
  setActiveSet: (id: string | null) => void;
  toggleSetSelection: (id: string) => void;
  clearSelection: () => void;
  selectAll: (ids: string[]) => void;
  deselectAll: () => void;

  // Actions — panels
  togglePanel: (panelId: PanelId) => void;
  expandPanel: (panelId: PanelId) => void;
  collapsePanel: (panelId: PanelId) => void;

  // Actions — sidebar visibility
  toggleGeneSearch: () => void;
  toggleLeftSidebar: () => void;

  // Actions — evaluate controls
  appendPositiveControls: (ids: string[]) => void;
  appendNegativeControls: (ids: string[]) => void;
  /** Pending control IDs set by the search sidebar, consumed by EvaluatePanel. */
  pendingPositiveControls: string[];
  pendingNegativeControls: string[];
  clearPendingControls: () => void;

  // Actions — experiment
  setLastExperiment: (experiment: Experiment | null, setId: string | null) => void;
  clearLastExperiment: () => void;

  // Actions — global
  reset: () => void;
}

// ---------------------------------------------------------------------------
// Initial state (extracted so `reset` can reuse it)
// ---------------------------------------------------------------------------

const initialState = {
  activeSetId: null as string | null,
  selectedSetIds: [] as string[],
  expandedPanels: new Set<PanelId>(),
  lastExperiment: null as Experiment | null,
  lastExperimentSetId: null as string | null,
  geneSearchOpen: false,
  leftSidebarOpen: true,
  pendingPositiveControls: [] as string[],
  pendingNegativeControls: [] as string[],
};

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useWorkbenchStore = create<WorkbenchState>()((set) => ({
  ...initialState,

  // -- Gene set selection actions ----------------------------------------------

  setActiveSet: (id) =>
    set((s) => ({
      activeSetId: id,
      // Clear stale experiment when switching gene sets
      ...(id !== s.lastExperimentSetId
        ? { lastExperiment: null, lastExperimentSetId: null }
        : {}),
    })),

  toggleSetSelection: (id) =>
    set((s) => ({
      selectedSetIds: s.selectedSetIds.includes(id)
        ? s.selectedSetIds.filter((sid) => sid !== id)
        : [...s.selectedSetIds, id],
    })),

  clearSelection: () => set({ selectedSetIds: [] }),

  selectAll: (ids) => set({ selectedSetIds: ids }),

  deselectAll: () => set({ selectedSetIds: [] }),

  // -- Panel actions --------------------------------------------------------

  togglePanel: (panelId) =>
    set((s) => {
      const next = new Set(s.expandedPanels);
      if (next.has(panelId)) {
        next.delete(panelId);
      } else {
        next.add(panelId);
      }
      return { expandedPanels: next };
    }),

  expandPanel: (panelId) =>
    set((s) => {
      if (s.expandedPanels.has(panelId)) return s;
      const next = new Set(s.expandedPanels);
      next.add(panelId);
      return { expandedPanels: next };
    }),

  collapsePanel: (panelId) =>
    set((s) => {
      if (!s.expandedPanels.has(panelId)) return s;
      const next = new Set(s.expandedPanels);
      next.delete(panelId);
      return { expandedPanels: next };
    }),

  // -- Gene search sidebar ---------------------------------------------------

  toggleGeneSearch: () => set((s) => ({ geneSearchOpen: !s.geneSearchOpen })),
  toggleLeftSidebar: () => set((s) => ({ leftSidebarOpen: !s.leftSidebarOpen })),

  // -- Evaluate controls ----------------------------------------------------

  appendPositiveControls: (ids) =>
    set((s) => ({
      pendingPositiveControls: [...s.pendingPositiveControls, ...ids],
    })),

  appendNegativeControls: (ids) =>
    set((s) => ({
      pendingNegativeControls: [...s.pendingNegativeControls, ...ids],
    })),

  clearPendingControls: () =>
    set({ pendingPositiveControls: [], pendingNegativeControls: [] }),

  // -- Experiment actions ----------------------------------------------------

  setLastExperiment: (experiment, setId) =>
    set({ lastExperiment: experiment, lastExperimentSetId: setId }),

  clearLastExperiment: () => set({ lastExperiment: null, lastExperimentSetId: null }),

  // -- Global ---------------------------------------------------------------

  reset: () =>
    set({
      activeSetId: null,
      selectedSetIds: [],
      expandedPanels: new Set<PanelId>(),
      lastExperiment: null,
      lastExperimentSetId: null,
      geneSearchOpen: false,
      leftSidebarOpen: true,
      pendingPositiveControls: [],
      pendingNegativeControls: [],
    }),
}));

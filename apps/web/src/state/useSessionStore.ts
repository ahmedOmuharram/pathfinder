/**
 * Session state store — selected site, strategy tracking, auth state.
 *
 * Persists site selection and per-site strategy IDs via Zustand persist
 * middleware. Transient state (auth, streaming, signals) stays memory-only.
 */

import { createPersistedStore } from "./middleware";
import { useStrategyStore } from "./strategy/store";
import { useWorkbenchStore } from "./useWorkbenchStore";
import type { NodeSelection } from "@/lib/types/nodeSelection";
import type {
  GeneSetPart,
  OptimizationSnapshot,
  ProblemFramePart,
} from "@pathfinder/shared";

interface SessionState {
  selectedSite: string;
  strategyId: string | null;
  /** Maps siteId -> last-used strategyId for cross-site restore. */
  strategyBySite: Record<string, string>;
  chatIsStreaming: boolean;

  chatPreviewVersion: number;
  pendingAskNode: NodeSelection | null;
  composerPrefill: { message: string } | null;
  /** Text that the next-mounted ChatThread should auto-submit. */
  pendingUserSubmission: { conversationId: string; content: string } | null;
  /** Bumped to force a ChatThread remount after revert. */
  chatResetCounter: number;

  // Stream-derived session state (from chat data-* parts)
  problemFrame: ProblemFramePart | null;
  lastGeneSet: GeneSetPart | null;
  optimizationProgress: OptimizationSnapshot | null;

  setSelectedSite: (siteId: string) => void;
  /** Switch site with full cleanup — clears strategy data and resets workbench. */
  switchSite: (siteId: string) => void;
  setStrategyId: (id: string | null) => void;
  setChatIsStreaming: (value: boolean) => void;

  bumpChatPreviewVersion: () => void;
  setPendingAskNode: (payload: NodeSelection | null) => void;
  setComposerPrefill: (payload: { message: string } | null) => void;
  setPendingUserSubmission: (
    payload: { conversationId: string; content: string } | null,
  ) => void;
  bumpChatResetCounter: () => void;

  // Stream-derived session setters (from chat data-* parts)
  setProblemFrame: (frame: ProblemFramePart) => void;
  recordGeneSet: (set: GeneSetPart) => void;
  setOptimizationProgress: (snapshot: OptimizationSnapshot) => void;
}

export const useSessionStore = createPersistedStore<SessionState>(
  "SessionStore",
  (set, get) => ({
    selectedSite: "veupathdb",
    strategyId: null,
    strategyBySite: {},
    chatIsStreaming: false,

    chatPreviewVersion: 0,
    pendingAskNode: null,
    composerPrefill: null,
    pendingUserSubmission: null,
    chatResetCounter: 0,

    problemFrame: null,
    lastGeneSet: null,
    optimizationProgress: null,

    setSelectedSite: (siteId) =>
      set((s) => {
        if (s.selectedSite === siteId) return s;
        return {
          selectedSite: siteId,
          strategyId: s.strategyBySite[siteId] ?? null,
        };
      }),

    switchSite: (siteId) => {
      if (get().selectedSite === siteId) return;
      set({ selectedSite: siteId, strategyId: null });
      useStrategyStore.getState().clear();
      useWorkbenchStore.getState().reset();
    },

    setStrategyId: (id) => {
      const site = get().selectedSite;
      set((s) => {
        if (s.strategyId === id && s.strategyBySite[site] === id) return s;
        const next = { ...s.strategyBySite };
        if (id !== null) {
          next[site] = id;
        } else {
          delete next[site];
        }
        return { strategyId: id, strategyBySite: next };
      });
    },

    setChatIsStreaming: (value) =>
      set((s) => (s.chatIsStreaming === value ? s : { chatIsStreaming: value })),

    bumpChatPreviewVersion: () =>
      set((s) => ({ chatPreviewVersion: s.chatPreviewVersion + 1 })),
    setPendingAskNode: (payload) =>
      set((s) => (s.pendingAskNode === payload ? s : { pendingAskNode: payload })),
    setComposerPrefill: (payload) =>
      set((s) => (s.composerPrefill === payload ? s : { composerPrefill: payload })),
    setPendingUserSubmission: (payload) => set({ pendingUserSubmission: payload }),
    bumpChatResetCounter: () =>
      set((s) => ({ chatResetCounter: s.chatResetCounter + 1 })),

    setProblemFrame: (frame) => set({ problemFrame: frame }),
    recordGeneSet: (geneSet) => set({ lastGeneSet: geneSet }),
    setOptimizationProgress: (snapshot) => set({ optimizationProgress: snapshot }),
  }),
  {
    name: "pathfinder-session",
    partialize: (s) => ({
      selectedSite: s.selectedSite,
      strategyId: s.strategyId,
      strategyBySite: s.strategyBySite,
    }),
  },
);

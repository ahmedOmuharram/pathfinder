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
  selectedSiteDisplayName: string;
  strategyId: string | null;
  /** Maps siteId -> last-used strategyId for cross-site restore. */
  strategyBySite: Record<string, string>;
  veupathdbSignedIn: boolean;
  veupathdbName: string | null;
  chatIsStreaming: boolean;

  chatPreviewVersion: number;
  pendingAskNode: NodeSelection | null;
  composerPrefill: { message: string } | null;

  authRefreshed: boolean;
  authStatusKnown: boolean;
  authVersion: number;

  // Stream-derived session state (from chat data-* parts)
  problemFrame: ProblemFramePart | null;
  lastGeneSet: GeneSetPart | null;
  optimizationProgress: OptimizationSnapshot | null;
  conversationTitle: string | null;

  setSelectedSite: (siteId: string) => void;
  /** Switch site with full cleanup — clears strategy data and resets workbench. */
  switchSite: (siteId: string) => void;
  setSelectedSiteInfo: (siteId: string, displayName: string) => void;
  setStrategyId: (id: string | null) => void;
  setVeupathdbAuth: (signedIn: boolean, name?: string | null) => void;
  setChatIsStreaming: (value: boolean) => void;

  bumpChatPreviewVersion: () => void;
  bumpAuthVersion: () => void;
  setPendingAskNode: (payload: NodeSelection | null) => void;
  setComposerPrefill: (payload: { message: string } | null) => void;
  setAuthRefreshed: (value: boolean) => void;
  setAuthStatusKnown: (value: boolean) => void;
  forceSignOut: () => void;

  // Stream-derived session setters (from chat data-* parts)
  setProblemFrame: (frame: ProblemFramePart) => void;
  recordGeneSet: (set: GeneSetPart) => void;
  setOptimizationProgress: (snapshot: OptimizationSnapshot) => void;
  setConversationTitle: (title: string) => void;
}

export const useSessionStore = createPersistedStore<SessionState>(
  "SessionStore",
  (set, get) => ({
    selectedSite: "veupathdb",
    selectedSiteDisplayName: "VEuPathDB",
    strategyId: null,
    strategyBySite: {},
    veupathdbSignedIn: false,
    veupathdbName: null,
    chatIsStreaming: false,

    chatPreviewVersion: 0,
    pendingAskNode: null,
    composerPrefill: null,
    authRefreshed: false,
    authStatusKnown: false,
    authVersion: 0,

    problemFrame: null,
    lastGeneSet: null,
    optimizationProgress: null,
    conversationTitle: null,

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

    setSelectedSiteInfo: (siteId, displayName) =>
      set((s) => {
        if (s.selectedSite === siteId) {
          return { selectedSite: siteId, selectedSiteDisplayName: displayName };
        }
        return {
          selectedSite: siteId,
          selectedSiteDisplayName: displayName,
          strategyId: s.strategyBySite[siteId] ?? null,
        };
      }),

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

    setVeupathdbAuth: (signedIn, name = null) =>
      set((s) =>
        s.veupathdbSignedIn === signedIn && s.veupathdbName === name
          ? s
          : { veupathdbSignedIn: signedIn, veupathdbName: name },
      ),
    setChatIsStreaming: (value) =>
      set((s) => (s.chatIsStreaming === value ? s : { chatIsStreaming: value })),

    bumpChatPreviewVersion: () =>
      set((s) => ({ chatPreviewVersion: s.chatPreviewVersion + 1 })),
    bumpAuthVersion: () => set((s) => ({ authVersion: s.authVersion + 1 })),
    setPendingAskNode: (payload) =>
      set((s) => (s.pendingAskNode === payload ? s : { pendingAskNode: payload })),
    setComposerPrefill: (payload) =>
      set((s) => (s.composerPrefill === payload ? s : { composerPrefill: payload })),
    setAuthRefreshed: (value) =>
      set((s) => (s.authRefreshed === value ? s : { authRefreshed: value })),
    setAuthStatusKnown: (value) =>
      set((s) => (s.authStatusKnown === value ? s : { authStatusKnown: value })),
    forceSignOut: () =>
      set({
        veupathdbSignedIn: false,
        veupathdbName: null,
        authRefreshed: false,
      }),

    setProblemFrame: (frame) => set({ problemFrame: frame }),
    recordGeneSet: (geneSet) => set({ lastGeneSet: geneSet }),
    setOptimizationProgress: (snapshot) => set({ optimizationProgress: snapshot }),
    setConversationTitle: (title) => set({ conversationTitle: title }),
  }),
  {
    name: "pathfinder-session",
    partialize: (s) => ({
      selectedSite: s.selectedSite,
      selectedSiteDisplayName: s.selectedSiteDisplayName,
      strategyId: s.strategyId,
      strategyBySite: s.strategyBySite,
    }),
  },
);

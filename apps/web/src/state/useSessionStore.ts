/**
 * Session state store (user, selected site)
 */

import { create } from "zustand";
import { setAuthTokenGetter } from "@/lib/api/auth";
import type { ChatMode } from "@pathfinder/shared";

export interface PendingExecutorSend {
  strategyId: string;
  message: string;
}

interface SessionState {
  selectedSite: string;
  selectedSiteDisplayName: string;
  strategyId: string | null;
  planSessionId: string | null;
  pendingExecutorSend: PendingExecutorSend | null;
  authToken: string | null;
  veupathdbSignedIn: boolean;
  veupathdbName: string | null;
  chatIsStreaming: boolean;

  /**
   * Chat mode is now **derived** from whether a strategyId is set.
   * Kept in the store for internal use and the plan->execute transition,
   * but never shown to the user via a toggle.
   */
  chatMode: ChatMode;

  /**
   * Links plan sessions to strategies they graduated into.
   * Key = planSessionId, Value = strategyId.
   * Used by the sidebar to hide graduated plans and show strategy instead.
   */
  linkedConversations: Record<string, string>;

  // --- Signals (replace window custom events) ---
  /** Monotonic counter; bump to tell sidebar to refresh. */
  planListVersion: number;
  /** Monotonic counter; bump to tell sidebar to reload chat preview. */
  chatPreviewVersion: number;
  /** Transient node selection payload from graph -> chat. */
  pendingAskNode: Record<string, unknown> | null;
  /** When true, the executor chat view should be activated. */
  openExecutorChat: boolean;
  /** Prefill content for the message composer. */
  composerPrefill: { mode: ChatMode; message: string } | null;

  setSelectedSite: (siteId: string) => void;
  setSelectedSiteInfo: (siteId: string, displayName: string) => void;
  setStrategyId: (id: string | null) => void;
  setPlanSessionId: (id: string | null) => void;
  setPendingExecutorSend: (payload: PendingExecutorSend | null) => void;
  setAuthToken: (token: string | null) => void;
  setVeupathdbAuth: (signedIn: boolean, name?: string | null) => void;
  setChatIsStreaming: (value: boolean) => void;
  /** Internal — set mode during plan->execute transition. */
  setChatMode: (mode: ChatMode) => void;
  /** Link a plan session to a strategy it graduated into. */
  linkConversation: (planSessionId: string, strategyId: string) => void;

  // Signal setters
  bumpPlanListVersion: () => void;
  bumpChatPreviewVersion: () => void;
  setPendingAskNode: (payload: Record<string, unknown> | null) => void;
  setOpenExecutorChat: (value: boolean) => void;
  setComposerPrefill: (payload: { mode: ChatMode; message: string } | null) => void;
}

const AUTH_TOKEN_STORAGE_KEY = "pathfinder-auth-token";
const LINKED_CONVERSATIONS_KEY = "pathfinder-linked-conversations";

const getInitialAuthToken = () => {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
};

const getInitialLinkedConversations = (): Record<string, string> => {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(LINKED_CONVERSATIONS_KEY);
    return raw ? (JSON.parse(raw) as Record<string, string>) : {};
  } catch {
    return {};
  }
};

export const useSessionStore = create<SessionState>()((set) => ({
  selectedSite: "plasmodb",
  selectedSiteDisplayName: "PlasmoDB",
  strategyId: null,
  planSessionId: null,
  pendingExecutorSend: null,
  authToken: getInitialAuthToken(),
  veupathdbSignedIn: false,
  veupathdbName: null,
  chatIsStreaming: false,
  chatMode: "plan",
  linkedConversations: getInitialLinkedConversations(),

  // Signals
  planListVersion: 0,
  chatPreviewVersion: 0,
  pendingAskNode: null,
  openExecutorChat: false,
  composerPrefill: null,

  setSelectedSite: (siteId) => set({ selectedSite: siteId }),
  setSelectedSiteInfo: (siteId, displayName) =>
    set({ selectedSite: siteId, selectedSiteDisplayName: displayName }),
  setStrategyId: (id) =>
    set({
      strategyId: id,
      // Auto-derive chatMode: if a strategy is selected, use execute mode.
      chatMode: id ? "execute" : "plan",
    }),
  setPlanSessionId: (id) => set({ planSessionId: id }),
  setPendingExecutorSend: (payload) => set({ pendingExecutorSend: payload }),
  setAuthToken: (token) => {
    if (typeof window !== "undefined") {
      if (token) {
        window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
      } else {
        window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
      }
    }
    set({ authToken: token });
  },
  setVeupathdbAuth: (signedIn, name = null) =>
    set({ veupathdbSignedIn: signedIn, veupathdbName: name }),
  setChatIsStreaming: (value) => set({ chatIsStreaming: value }),
  setChatMode: (mode) => set({ chatMode: mode }),
  linkConversation: (planSessionId, strategyId) =>
    set((s) => {
      const next = { ...s.linkedConversations, [planSessionId]: strategyId };
      if (typeof window !== "undefined") {
        window.localStorage.setItem(LINKED_CONVERSATIONS_KEY, JSON.stringify(next));
      }
      return { linkedConversations: next };
    }),

  // Signal setters
  bumpPlanListVersion: () => set((s) => ({ planListVersion: s.planListVersion + 1 })),
  bumpChatPreviewVersion: () =>
    set((s) => ({ chatPreviewVersion: s.chatPreviewVersion + 1 })),
  setPendingAskNode: (payload) => set({ pendingAskNode: payload }),
  setOpenExecutorChat: (value) => set({ openExecutorChat: value }),
  setComposerPrefill: (payload) => set({ composerPrefill: payload }),
}));

// Inject token getter for transport-layer helpers (keeps `lib/api/*` independent of `state/*`).
setAuthTokenGetter(() => useSessionStore.getState().authToken);

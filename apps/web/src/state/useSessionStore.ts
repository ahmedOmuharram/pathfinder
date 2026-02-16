/**
 * Session state store (user, selected site)
 */

import { create } from "zustand";
import { setAuthTokenGetter } from "@/lib/api/auth";
import type { ChatMode } from "@pathfinder/shared";

interface SessionState {
  selectedSite: string;
  selectedSiteDisplayName: string;
  strategyId: string | null;
  planSessionId: string | null;
  authToken: string | null;
  veupathdbSignedIn: boolean;
  veupathdbName: string | null;
  chatIsStreaming: boolean;

  /**
   * Links plan sessions to strategies they graduated into.
   * Key = planSessionId, Value = strategyId.
   * Used by the sidebar to hide graduated plans and show strategy instead.
   */
  linkedConversations: Record<string, string>;

  /** Monotonic counter; bump to tell sidebar to refresh. */
  planListVersion: number;
  /** Monotonic counter; bump to tell sidebar to reload chat preview. */
  chatPreviewVersion: number;
  /** Transient node selection payload from graph -> chat. */
  pendingAskNode: Record<string, unknown> | null;
  /** Prefill content for the message composer. */
  composerPrefill: { mode: ChatMode; message: string } | null;

  /** Whether the VEuPathDB auth token has been refreshed in this session. */
  authRefreshed: boolean;

  setSelectedSite: (siteId: string) => void;
  setSelectedSiteInfo: (siteId: string, displayName: string) => void;
  setStrategyId: (id: string | null) => void;
  setPlanSessionId: (id: string | null) => void;
  setAuthToken: (token: string | null) => void;
  setVeupathdbAuth: (signedIn: boolean, name?: string | null) => void;
  setChatIsStreaming: (value: boolean) => void;
  /** Link a plan session to a strategy it graduated into. */
  linkConversation: (planSessionId: string, strategyId: string) => void;

  // Signal setters
  bumpPlanListVersion: () => void;
  bumpChatPreviewVersion: () => void;
  setPendingAskNode: (payload: Record<string, unknown> | null) => void;
  setComposerPrefill: (payload: { mode: ChatMode; message: string } | null) => void;
  setAuthRefreshed: (value: boolean) => void;
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
  authToken: getInitialAuthToken(),
  veupathdbSignedIn: false,
  veupathdbName: null,
  chatIsStreaming: false,
  linkedConversations: getInitialLinkedConversations(),

  // Signals
  planListVersion: 0,
  chatPreviewVersion: 0,
  pendingAskNode: null,
  composerPrefill: null,
  authRefreshed: false,

  setSelectedSite: (siteId) => set({ selectedSite: siteId }),
  setSelectedSiteInfo: (siteId, displayName) =>
    set({ selectedSite: siteId, selectedSiteDisplayName: displayName }),
  setStrategyId: (id) => set({ strategyId: id }),
  setPlanSessionId: (id) => set({ planSessionId: id }),
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
  setComposerPrefill: (payload) => set({ composerPrefill: payload }),
  setAuthRefreshed: (value) => set({ authRefreshed: value }),
}));

// Inject token getter for transport-layer helpers (keeps `lib/api/*` independent of `state/*`).
setAuthTokenGetter(() => useSessionStore.getState().authToken);

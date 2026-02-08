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
  chatMode: ChatMode;
  setSelectedSite: (siteId: string) => void;
  setSelectedSiteInfo: (siteId: string, displayName: string) => void;
  setStrategyId: (id: string | null) => void;
  setPlanSessionId: (id: string | null) => void;
  setPendingExecutorSend: (payload: PendingExecutorSend | null) => void;
  setAuthToken: (token: string | null) => void;
  setVeupathdbAuth: (signedIn: boolean, name?: string | null) => void;
  setChatIsStreaming: (value: boolean) => void;
  setChatMode: (mode: ChatMode) => void;
}

const AUTH_TOKEN_STORAGE_KEY = "pathfinder-auth-token";

const getInitialAuthToken = () => {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
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
  setSelectedSite: (siteId) => set({ selectedSite: siteId }),
  setSelectedSiteInfo: (siteId, displayName) =>
    set({ selectedSite: siteId, selectedSiteDisplayName: displayName }),
  setStrategyId: (id) => set({ strategyId: id }),
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
}));

// Inject token getter for transport-layer helpers (keeps `lib/api/*` independent of `state/*`).
setAuthTokenGetter(() => useSessionStore.getState().authToken);

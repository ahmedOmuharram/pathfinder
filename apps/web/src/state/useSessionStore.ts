/**
 * Session state store (user, selected site)
 */

import { create } from "zustand";
import { setAuthTokenGetter } from "@/lib/api/auth";

interface SessionState {
  selectedSite: string;
  selectedSiteDisplayName: string;
  strategyId: string | null;
  authToken: string | null;
  veupathdbSignedIn: boolean;
  veupathdbName: string | null;
  setSelectedSite: (siteId: string) => void;
  setSelectedSiteInfo: (siteId: string, displayName: string) => void;
  setStrategyId: (id: string | null) => void;
  setAuthToken: (token: string | null) => void;
  setVeupathdbAuth: (signedIn: boolean, name?: string | null) => void;
}

export const useSessionStore = create<SessionState>()((set) => ({
  selectedSite: "plasmodb",
  selectedSiteDisplayName: "PlasmoDB",
  strategyId: null,
  authToken: null,
  veupathdbSignedIn: false,
  veupathdbName: null,
  setSelectedSite: (siteId) => set({ selectedSite: siteId }),
  setSelectedSiteInfo: (siteId, displayName) =>
    set({ selectedSite: siteId, selectedSiteDisplayName: displayName }),
  setStrategyId: (id) => set({ strategyId: id }),
  setAuthToken: (token) => set({ authToken: token }),
  setVeupathdbAuth: (signedIn, name = null) =>
    set({ veupathdbSignedIn: signedIn, veupathdbName: name }),
}));

// Inject token getter for transport-layer helpers (keeps `lib/api/*` independent of `state/*`).
setAuthTokenGetter(() => useSessionStore.getState().authToken);


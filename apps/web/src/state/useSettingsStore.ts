/**
 * User settings store — persisted via Zustand persist middleware.
 *
 * Stores debug toggles and WDK delete preference.
 */

import { createPersistedStore } from "./middleware";

interface SettingsState {
  showRawToolCalls: boolean;
  showTokenUsage: boolean;
  deleteFromWdk: boolean;

  setShowRawToolCalls: (show: boolean) => void;
  setShowTokenUsage: (show: boolean) => void;
  setDeleteFromWdk: (v: boolean) => void;
  resetToDefaults: () => void;
}

const DEFAULTS = {
  showRawToolCalls: false,
  showTokenUsage: true,
  deleteFromWdk: false,
} as const;

export const useSettingsStore = createPersistedStore<SettingsState>(
  "SettingsStore",
  (set) => ({
    ...DEFAULTS,

    setShowRawToolCalls: (show) => set({ showRawToolCalls: show }),
    setShowTokenUsage: (show) => set({ showTokenUsage: show }),
    setDeleteFromWdk: (v) => set({ deleteFromWdk: v }),
    resetToDefaults: () => set({ ...DEFAULTS }),
  }),
  {
    name: "pathfinder-settings",
    partialize: (s) => ({
      showRawToolCalls: s.showRawToolCalls,
      showTokenUsage: s.showTokenUsage,
      deleteFromWdk: s.deleteFromWdk,
    }),
  },
);

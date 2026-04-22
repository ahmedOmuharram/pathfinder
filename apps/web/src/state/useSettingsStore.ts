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
  firstRunHintDismissed: boolean;

  setShowRawToolCalls: (show: boolean) => void;
  setShowTokenUsage: (show: boolean) => void;
  setDeleteFromWdk: (v: boolean) => void;
  dismissFirstRunHint: () => void;
  resetToDefaults: () => void;
}

const DEFAULTS = {
  showRawToolCalls: false,
  showTokenUsage: true,
  deleteFromWdk: false,
  firstRunHintDismissed: false,
} as const;

export const useSettingsStore = createPersistedStore<SettingsState>(
  "SettingsStore",
  (set) => ({
    ...DEFAULTS,

    setShowRawToolCalls: (show) => set({ showRawToolCalls: show }),
    setShowTokenUsage: (show) => set({ showTokenUsage: show }),
    setDeleteFromWdk: (v) => set({ deleteFromWdk: v }),
    dismissFirstRunHint: () => set({ firstRunHintDismissed: true }),
    resetToDefaults: () => set({ ...DEFAULTS }),
  }),
  {
    name: "pathfinder-settings",
    partialize: (s) => ({
      showRawToolCalls: s.showRawToolCalls,
      showTokenUsage: s.showTokenUsage,
      deleteFromWdk: s.deleteFromWdk,
      firstRunHintDismissed: s.firstRunHintDismissed,
    }),
  },
);

export const PERSISTED_STORE_KEYS = [
  "pathfinder-settings",
  "pathfinder-left-sidebar",
  "pathfinder-right-rail",
] as const;

export function resetAllPersistedSettings(): void {
  if (typeof window === "undefined") return;
  for (const key of PERSISTED_STORE_KEYS) {
    window.localStorage.removeItem(key);
  }
}

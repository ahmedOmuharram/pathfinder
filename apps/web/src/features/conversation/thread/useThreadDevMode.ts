"use client";

import { useSettingsStore } from "@/state/useSettingsStore";

export interface ThreadDevMode {
  showRaw: boolean;
  showUsage: boolean;
}

/** The thread's whole dev mode: the two settings flags, read in one place. */
export function useThreadDevMode(): ThreadDevMode {
  const showRaw = useSettingsStore((state) => state.showRawToolCalls);
  const showUsage = useSettingsStore((state) => state.showTokenUsage);
  return { showRaw, showUsage };
}

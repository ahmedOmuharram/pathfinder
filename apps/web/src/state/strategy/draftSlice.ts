import type { StateCreator } from "zustand";
import type { DevtoolsMutators } from "@/state/middleware";
import type { DraftSlice, StrategyState } from "./types";

export const createDraftSlice: StateCreator<
  StrategyState,
  DevtoolsMutators,
  [],
  DraftSlice
> = (set) => ({
  lastFailedPush: null,

  setLastFailedPush: (payload) => {
    set({ lastFailedPush: payload });
  },

  clear: () => {
    set({
      lastFailedPush: null,
      stepLifecycleById: {},
      undoStack: [],
      redoStack: [],
    });
  },
});

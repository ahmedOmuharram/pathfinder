import type { StateCreator } from "zustand";
import type { DevtoolsMutators } from "@/state/middleware";
import type { DraftSlice, StrategyState } from "./types";

export const createDraftSlice: StateCreator<
  StrategyState,
  DevtoolsMutators,
  [],
  DraftSlice
> = (set) => ({
  lastFailedOperation: null,

  setLastFailedOperation: (payload) => {
    set({ lastFailedOperation: payload });
  },

  clear: () => {
    set({
      lastFailedOperation: null,
      stepLifecycleById: {},
      undoStack: [],
      redoStack: [],
    });
  },
});

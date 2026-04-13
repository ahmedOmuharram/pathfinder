/**
 * Meta slice — graph validation status, stream-derived snapshot/patch state.
 */

import type { StateCreator } from "zustand";
import type { DevtoolsMutators } from "@/state/middleware";
import type { StrategyState, MetaSlice } from "./types";

export const createMetaSlice: StateCreator<StrategyState, DevtoolsMutators, [], MetaSlice> = (
  set,
) => ({
  graphValidationStatus: {},
  latestGraphSnapshot: null,
  latestStrategyMeta: null,
  lastStrategyPatch: null,

  setGraphValidationStatus: (id, hasErrors) =>
    set((state) => ({
      graphValidationStatus: {
        ...state.graphValidationStatus,
        [id]: hasErrors,
      },
    })),

  applyGraphSnapshot: (snapshot) => set({ latestGraphSnapshot: snapshot }),
  setLatestStrategyMeta: (meta) => set({ latestStrategyMeta: meta }),
  applyPatch: (patch) => set({ lastStrategyPatch: patch }),
});

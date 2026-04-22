/**
 * Meta slice — graph validation status. Stream-derived snapshot/patch state
 * was removed; AI streaming events drive query invalidation directly.
 */

import type { StateCreator } from "zustand";
import type { DevtoolsMutators } from "@/state/middleware";
import type { MetaSlice, StrategyState } from "./types";

export const createMetaSlice: StateCreator<
  StrategyState,
  DevtoolsMutators,
  [],
  MetaSlice
> = (set) => ({
  graphValidationStatus: {},

  setGraphValidationStatus: (id, hasErrors) =>
    set((state) => ({
      graphValidationStatus: {
        ...state.graphValidationStatus,
        [id]: hasErrors,
      },
    })),
});

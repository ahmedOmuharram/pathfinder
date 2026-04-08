/**
 * Meta slice — graph validation status and other cross-cutting metadata.
 */

import type { StateCreator } from "zustand";
import type { DevtoolsMutators } from "@/state/middleware";
import type { StrategyState, MetaSlice } from "./types";

export const createMetaSlice: StateCreator<StrategyState, DevtoolsMutators, [], MetaSlice> = (
  set,
) => ({
  graphValidationStatus: {},

  setGraphValidationStatus: (id, hasErrors) =>
    set((state) => ({
      graphValidationStatus: {
        ...state.graphValidationStatus,
        [id]: hasErrors,
      },
    })),
});

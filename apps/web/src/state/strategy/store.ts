/**
 * Composed strategy store — merges all slices into a single Zustand store.
 */

import { createStore } from "@/state/middleware";
import type { StrategyState } from "./types";
import { createDraftSlice } from "./draftSlice";
import { createHistorySlice } from "./historySlice";
import { createLifecycleSlice } from "./lifecycleSlice";
import { createListSlice } from "./listSlice";
import { createMetaSlice } from "./metaSlice";

export const useStrategyStore = createStore<StrategyState>(
  "StrategyStore",
  (...args) => ({
    ...createDraftSlice(...args),
    ...createHistorySlice(...args),
    ...createLifecycleSlice(...args),
    ...createListSlice(...args),
    ...createMetaSlice(...args),
  }),
);

import { create } from "zustand";
import type { MemoryItem, MemoryListResponse } from "@pathfinder/shared";

export interface MemoriesState {
  geneSets: MemoryItem[];
  strategies: MemoryItem[];
  preferences: MemoryItem[];
  knowledge: MemoryItem[];
  loading: boolean;
  error: string | null;
  setLoading: (v: boolean) => void;
  setError: (e: string | null) => void;
  setGroups: (groups: MemoryListResponse) => void;
  reset: () => void;
}

const INITIAL = {
  geneSets: [],
  strategies: [],
  preferences: [],
  knowledge: [],
  loading: false,
  error: null,
} satisfies Pick<
  MemoriesState,
  "geneSets" | "strategies" | "preferences" | "knowledge" | "loading" | "error"
>;

export const useMemoriesStore = create<MemoriesState>((set) => ({
  ...INITIAL,
  setLoading: (v) => set({ loading: v }),
  setError: (e) => set({ error: e }),
  setGroups: (groups) =>
    set({
      geneSets: groups.geneSets,
      strategies: groups.strategies,
      preferences: groups.preferences,
      knowledge: groups.knowledge,
    }),
  reset: () => set({ ...INITIAL }),
}));

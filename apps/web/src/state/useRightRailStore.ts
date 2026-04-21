import { createPersistedStore } from "./middleware";

export const RIGHT_RAIL_PANELS = [
  "strategy",
  "plan",
  "tasks",
  "memories",
  "scratchpad",
] as const;

export type RightRailPanel = (typeof RIGHT_RAIL_PANELS)[number];

interface LastSeen {
  strategyStepCount: number;
  planId: string | null;
}

const DEFAULT_LAST_SEEN: LastSeen = {
  strategyStepCount: 0,
  planId: null,
};

interface RightRailState {
  openPanel: RightRailPanel | null;
  lastSeen: LastSeen;

  openPanelId: (panel: RightRailPanel, markers: Partial<LastSeen>) => void;
  togglePanel: (panel: RightRailPanel, markers: Partial<LastSeen>) => void;
  closePanel: () => void;
}

export const useRightRailStore = createPersistedStore<RightRailState>(
  "RightRailStore",
  (set, get) => ({
    openPanel: null,
    lastSeen: { ...DEFAULT_LAST_SEEN },

    openPanelId: (panel, markers) =>
      set((s) => ({
        openPanel: panel,
        lastSeen: { ...s.lastSeen, ...markers },
      })),

    togglePanel: (panel, markers) => {
      const current = get().openPanel;
      if (current === panel) {
        set({ openPanel: null });
        return;
      }
      set((s) => ({
        openPanel: panel,
        lastSeen: { ...s.lastSeen, ...markers },
      }));
    },

    closePanel: () => set({ openPanel: null }),
  }),
  {
    name: "pathfinder-right-rail",
    partialize: (s) => ({ openPanel: s.openPanel, lastSeen: s.lastSeen }),
  },
);

interface LeftSidebarState {
  collapsed: boolean;
  toggle: () => void;
  setCollapsed: (value: boolean) => void;
}

export const useLeftSidebarStore = createPersistedStore<LeftSidebarState>(
  "LeftSidebarStore",
  (set) => ({
    collapsed: false,
    toggle: () => set((s) => ({ collapsed: !s.collapsed })),
    setCollapsed: (value) => set({ collapsed: value }),
  }),
  {
    name: "pathfinder-left-sidebar",
    partialize: (s) => ({ collapsed: s.collapsed }),
  },
);

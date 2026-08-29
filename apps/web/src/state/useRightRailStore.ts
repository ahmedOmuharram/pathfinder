import { createPersistedStore } from "./middleware";

export const RIGHT_RAIL_PANELS = [
  "strategy",
  "tasks",
  "memories",
  "scratchpad",
  "ledger",
  "eda",
] as const;

export type RightRailPanel = (typeof RIGHT_RAIL_PANELS)[number];

interface LastSeen {
  strategyStepCount: number;
  ledgerCount: number;
  scratchpadCount: number;
  taskCount: number;
  memoryCount: number;
  edaCount: number;
}

const DEFAULT_LAST_SEEN: LastSeen = {
  strategyStepCount: 0,
  ledgerCount: 0,
  scratchpadCount: 0,
  taskCount: 0,
  memoryCount: 0,
  edaCount: 0,
};

interface RightRailState {
  openPanel: RightRailPanel | null;
  lastSeen: LastSeen;
  autoOpenedConversation: string | null;
  ledgerSeen: Record<string, Record<string, string>>;

  openPanelId: (panel: RightRailPanel, markers: Partial<LastSeen>) => void;
  togglePanel: (panel: RightRailPanel, markers: Partial<LastSeen>) => void;
  closePanel: () => void;
  autoOpen: (conversationId: string, panel: RightRailPanel) => void;
  markLedgerTabSeen: (conversationId: string, tab: string, signature: string) => void;
}

export const useRightRailStore = createPersistedStore<RightRailState>(
  "RightRailStore",
  (set, get) => ({
    openPanel: null,
    lastSeen: { ...DEFAULT_LAST_SEEN },
    autoOpenedConversation: null,
    ledgerSeen: {},

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

    autoOpen: (conversationId, panel) => {
      if (get().autoOpenedConversation === conversationId) return;
      set((s) => ({
        autoOpenedConversation: conversationId,
        openPanel: s.openPanel ?? panel,
      }));
    },

    markLedgerTabSeen: (conversationId, tab, signature) =>
      set((s) => ({
        ledgerSeen: {
          ...s.ledgerSeen,
          [conversationId]: { ...s.ledgerSeen[conversationId], [tab]: signature },
        },
      })),
  }),
  {
    name: "pathfinder-right-rail",
    partialize: (s) => ({
      openPanel: s.openPanel,
      lastSeen: s.lastSeen,
      autoOpenedConversation: s.autoOpenedConversation,
      ledgerSeen: s.ledgerSeen,
    }),
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

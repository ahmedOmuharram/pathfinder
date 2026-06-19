// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from "vitest";

import { useRightRailStore, useLeftSidebarStore } from "./useRightRailStore";

beforeEach(() => {
  useRightRailStore.setState({
    openPanel: null,
    autoOpenedConversation: null,
    ledgerSeen: {},
    lastSeen: {
      strategyStepCount: 0,
      ledgerCount: 0,
      scratchpadCount: 0,
      taskCount: 0,
      memoryCount: 0,
    },
  });
  useLeftSidebarStore.setState({ collapsed: false });
});

describe("useRightRailStore", () => {
  it("openPanelId opens a panel and merges last-seen markers", () => {
    useRightRailStore.getState().openPanelId("strategy", { strategyStepCount: 4 });
    const s = useRightRailStore.getState();
    expect(s.openPanel).toBe("strategy");
    expect(s.lastSeen.strategyStepCount).toBe(4);
    expect(s.lastSeen.ledgerCount).toBe(0);
  });

  it("togglePanel opens a different panel, closes the same one", () => {
    const s = useRightRailStore.getState();
    s.togglePanel("memories", { memoryCount: 1 });
    expect(useRightRailStore.getState().openPanel).toBe("memories");
    expect(useRightRailStore.getState().lastSeen.memoryCount).toBe(1);

    // toggling the already-open panel closes it
    s.togglePanel("memories", { memoryCount: 2 });
    expect(useRightRailStore.getState().openPanel).toBeNull();

    // toggling a different panel switches to it
    s.togglePanel("tasks", {});
    expect(useRightRailStore.getState().openPanel).toBe("tasks");
  });

  it("closePanel clears the open panel", () => {
    useRightRailStore.getState().openPanelId("memories", {});
    useRightRailStore.getState().closePanel();
    expect(useRightRailStore.getState().openPanel).toBeNull();
  });

  it("autoOpen opens the panel once per conversation and respects an open panel", () => {
    useRightRailStore.getState().autoOpen("c1", "ledger");
    expect(useRightRailStore.getState().openPanel).toBe("ledger");
    expect(useRightRailStore.getState().autoOpenedConversation).toBe("c1");

    // user switches away; auto-open for the same conversation must not reopen
    useRightRailStore.getState().togglePanel("strategy", {});
    useRightRailStore.getState().autoOpen("c1", "ledger");
    expect(useRightRailStore.getState().openPanel).toBe("strategy");

    // a new conversation auto-opens ledger again
    useRightRailStore.getState().closePanel();
    useRightRailStore.getState().autoOpen("c2", "ledger");
    expect(useRightRailStore.getState().openPanel).toBe("ledger");
  });

  it("markLedgerTabSeen records signatures keyed by conversation and tab", () => {
    useRightRailStore.getState().markLedgerTabSeen("c1", "frame", "sig-frame");
    useRightRailStore.getState().markLedgerTabSeen("c1", "plan", "sig-plan");
    useRightRailStore.getState().markLedgerTabSeen("c2", "frame", "other");

    const { ledgerSeen } = useRightRailStore.getState();
    expect(ledgerSeen["c1"]).toEqual({ frame: "sig-frame", plan: "sig-plan" });
    expect(ledgerSeen["c2"]).toEqual({ frame: "other" });
  });
});

describe("useLeftSidebarStore", () => {
  it("toggle flips collapsed and setCollapsed sets it", () => {
    const s = useLeftSidebarStore.getState();
    s.toggle();
    expect(useLeftSidebarStore.getState().collapsed).toBe(true);
    s.setCollapsed(false);
    expect(useLeftSidebarStore.getState().collapsed).toBe(false);
  });
});

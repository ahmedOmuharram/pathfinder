// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from "vitest";

import {
  RIGHT_RAIL_PANELS,
  lastSeenFor,
  useRightRailStore,
  useLeftSidebarStore,
} from "./useRightRailStore";

beforeEach(() => {
  useRightRailStore.setState({
    openPanel: null,
    autoOpenedConversation: null,
    ledgerSeen: {},
    lastSeen: {},
  });
  useLeftSidebarStore.setState({ collapsed: false });
});

describe("RIGHT_RAIL_PANELS", () => {
  it("carries the eda panel", () => {
    expect(RIGHT_RAIL_PANELS).toEqual([
      "strategy",
      "tasks",
      "memories",
      "scratchpad",
      "ledger",
      "eda",
    ]);
  });
});

describe("useRightRailStore", () => {
  it("openPanelId opens a panel and merges last-seen markers for that conversation", () => {
    useRightRailStore
      .getState()
      .openPanelId("c1", "strategy", { strategyStepCount: 4 });
    const s = useRightRailStore.getState();
    expect(s.openPanel).toBe("strategy");
    expect(lastSeenFor(s.lastSeen, "c1").strategyStepCount).toBe(4);
    expect(lastSeenFor(s.lastSeen, "c1").ledgerCount).toBe(0);
  });

  it("keeps one conversation's markers out of another's", () => {
    useRightRailStore.getState().openPanelId("c1", "tasks", { taskCount: 3 });
    const seen = useRightRailStore.getState().lastSeen;
    expect(lastSeenFor(seen, "c1").taskCount).toBe(3);
    expect(lastSeenFor(seen, "c2").taskCount).toBe(0);
  });

  it("openPanelId records the eda marker so the dot clears", () => {
    useRightRailStore.getState().openPanelId("c1", "eda", { edaCount: 3 });
    const s = useRightRailStore.getState();
    expect(s.openPanel).toBe("eda");
    expect(lastSeenFor(s.lastSeen, "c1").edaCount).toBe(3);
  });

  it("togglePanel opens a different panel, closes the same one", () => {
    const s = useRightRailStore.getState();
    s.togglePanel("c1", "memories", { memoryCount: 1 });
    expect(useRightRailStore.getState().openPanel).toBe("memories");
    expect(lastSeenFor(useRightRailStore.getState().lastSeen, "c1").memoryCount).toBe(
      1,
    );

    s.togglePanel("c1", "memories", { memoryCount: 2 });
    expect(useRightRailStore.getState().openPanel).toBeNull();

    s.togglePanel("c1", "tasks", {});
    expect(useRightRailStore.getState().openPanel).toBe("tasks");
  });

  it("closePanel clears the open panel", () => {
    useRightRailStore.getState().openPanelId("c1", "memories", {});
    useRightRailStore.getState().closePanel();
    expect(useRightRailStore.getState().openPanel).toBe(null);
  });

  it("autoOpen opens the ledger once per conversation", () => {
    useRightRailStore.getState().autoOpen("c1", "ledger");
    expect(useRightRailStore.getState().openPanel).toBe("ledger");
    expect(useRightRailStore.getState().autoOpenedConversation).toBe("c1");
  });

  it("autoOpen leaves a panel the researcher already opened", () => {
    useRightRailStore.getState().togglePanel("c1", "strategy", {});
    useRightRailStore.getState().autoOpen("c1", "ledger");
    expect(useRightRailStore.getState().openPanel).toBe("strategy");
  });

  it("autoOpen runs again on another conversation", () => {
    useRightRailStore.getState().closePanel();
    useRightRailStore.getState().autoOpen("c2", "ledger");
    expect(useRightRailStore.getState().openPanel).toBe("ledger");
  });

  it("markLedgerTabSeen keys signatures by conversation and tab", () => {
    useRightRailStore.getState().markLedgerTabSeen("c1", "frame", "sig-frame");
    useRightRailStore.getState().markLedgerTabSeen("c1", "plan", "sig-plan");
    useRightRailStore.getState().markLedgerTabSeen("c2", "frame", "other");

    const { ledgerSeen } = useRightRailStore.getState();
    expect(ledgerSeen["c1"]).toEqual({ frame: "sig-frame", plan: "sig-plan" });
    expect(ledgerSeen["c2"]).toEqual({ frame: "other" });
  });
});

describe("useLeftSidebarStore", () => {
  it("toggles and sets collapsed", () => {
    useLeftSidebarStore.getState().toggle();
    expect(useLeftSidebarStore.getState().collapsed).toBe(true);
    useLeftSidebarStore.getState().setCollapsed(false);
    expect(useLeftSidebarStore.getState().collapsed).toBe(false);
  });
});

// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from "vitest";

import { useRightRailStore, useLeftSidebarStore } from "./useRightRailStore";

beforeEach(() => {
  useRightRailStore.setState({
    openPanel: null,
    lastSeen: { strategyStepCount: 0, planId: null },
  });
  useLeftSidebarStore.setState({ collapsed: false });
});

describe("useRightRailStore", () => {
  it("openPanelId opens a panel and merges last-seen markers", () => {
    useRightRailStore.getState().openPanelId("strategy", { strategyStepCount: 4 });
    const s = useRightRailStore.getState();
    expect(s.openPanel).toBe("strategy");
    expect(s.lastSeen.strategyStepCount).toBe(4);
    expect(s.lastSeen.planId).toBeNull();
  });

  it("togglePanel opens a different panel, closes the same one", () => {
    const s = useRightRailStore.getState();
    s.togglePanel("plan", { planId: "p1" });
    expect(useRightRailStore.getState().openPanel).toBe("plan");
    expect(useRightRailStore.getState().lastSeen.planId).toBe("p1");

    // toggling the already-open panel closes it
    s.togglePanel("plan", { planId: "p2" });
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

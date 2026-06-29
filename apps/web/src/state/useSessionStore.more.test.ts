// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from "vitest";
import type { GeneSetPart, OptimizationSnapshot } from "@pathfinder/shared";

import { useSessionStore } from "./useSessionStore";

beforeEach(() => {
  useSessionStore.setState({
    selectedSite: "veupathdb",
    strategyId: null,
    strategyBySite: {},
    chatIsStreaming: false,
    chatPreviewVersion: 0,
    pendingAskNode: null,
    composerPrefill: null,
    pendingUserSubmission: null,
    chatResetCounter: 0,
    lastGeneSet: null,
    optimizationProgress: null,
  });
});

describe("useSessionStore — site + strategy", () => {
  it("setStrategyId remembers the id per site, restored on setSelectedSite", () => {
    const s = useSessionStore.getState();
    s.setStrategyId("strat-1");
    expect(useSessionStore.getState().strategyId).toBe("strat-1");

    // Switching to a fresh site clears the visible strategy id.
    s.setSelectedSite("toxodb");
    expect(useSessionStore.getState().selectedSite).toBe("toxodb");
    expect(useSessionStore.getState().strategyId).toBeNull();

    // Returning restores the remembered id for the original site.
    s.setSelectedSite("veupathdb");
    expect(useSessionStore.getState().strategyId).toBe("strat-1");
  });

  it("setSelectedSite is a no-op for the current site", () => {
    const before = useSessionStore.getState();
    before.setSelectedSite("veupathdb");
    expect(useSessionStore.getState()).toBe(before);
  });

  it("switchSite clears the strategy and is a no-op for the same site", () => {
    const s = useSessionStore.getState();
    s.setStrategyId("strat-9");
    s.switchSite("cryptodb");
    expect(useSessionStore.getState().selectedSite).toBe("cryptodb");
    expect(useSessionStore.getState().strategyId).toBeNull();

    const snap = useSessionStore.getState();
    snap.switchSite("cryptodb"); // same site → early return, no state change
    expect(useSessionStore.getState().selectedSite).toBe("cryptodb");
  });
});

describe("useSessionStore — chat + stream-derived setters", () => {
  it("toggles streaming and skips redundant updates", () => {
    const s = useSessionStore.getState();
    s.setChatIsStreaming(true);
    expect(useSessionStore.getState().chatIsStreaming).toBe(true);
    const same = useSessionStore.getState();
    same.setChatIsStreaming(true); // no-op
    expect(useSessionStore.getState()).toBe(same);
  });

  it("bumps preview + reset counters", () => {
    const s = useSessionStore.getState();
    s.bumpChatPreviewVersion();
    s.bumpChatPreviewVersion();
    expect(useSessionStore.getState().chatPreviewVersion).toBe(2);
    s.bumpChatResetCounter();
    expect(useSessionStore.getState().chatResetCounter).toBe(1);
  });

  it("sets composer prefill, pending submission and pending ask node", () => {
    const s = useSessionStore.getState();
    s.setComposerPrefill({ message: "hello" });
    expect(useSessionStore.getState().composerPrefill?.message).toBe("hello");
    s.setPendingUserSubmission({ conversationId: "c1", content: "go" });
    expect(useSessionStore.getState().pendingUserSubmission?.content).toBe("go");
    s.setPendingAskNode(null);
    const snap = useSessionStore.getState();
    snap.setPendingAskNode(null); // same value → no-op
    expect(useSessionStore.getState()).toBe(snap);
  });

  it("records stream-derived gene set and optimization", () => {
    const s = useSessionStore.getState();
    const geneSet = { name: "set" } as unknown as GeneSetPart;
    const snapshot = { trial: 1 } as unknown as OptimizationSnapshot;
    s.recordGeneSet(geneSet);
    s.setOptimizationProgress(snapshot);
    const st = useSessionStore.getState();
    expect(st.lastGeneSet).toBe(geneSet);
    expect(st.optimizationProgress).toBe(snapshot);
  });
});

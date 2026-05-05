import { describe, expect, it, beforeEach } from "vitest";
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
  });
});

describe("state/useSessionStore", () => {
  it("setSelectedSite updates selected site", () => {
    useSessionStore.getState().setSelectedSite("tritrypdb");
    expect(useSessionStore.getState().selectedSite).toBe("tritrypdb");
  });

  it("setStrategyId updates strategyId and strategyBySite atomically", () => {
    useSessionStore.getState().setStrategyId("s-123");
    const s = useSessionStore.getState();
    expect(s.strategyId).toBe("s-123");
    expect(s.strategyBySite).toEqual({ veupathdb: "s-123" });
  });

  it("setStrategyId(null) removes entry from strategyBySite", () => {
    useSessionStore.getState().setStrategyId("s-123");
    useSessionStore.getState().setStrategyId(null);
    const s = useSessionStore.getState();
    expect(s.strategyId).toBeNull();
    expect(s.strategyBySite).toEqual({});
  });

  it("switching site restores strategyId from strategyBySite", () => {
    useSessionStore.getState().setStrategyId("s-veu");
    useSessionStore.getState().setSelectedSite("toxodb");
    expect(useSessionStore.getState().strategyId).toBeNull();
    useSessionStore.getState().setStrategyId("s-toxo");
    useSessionStore.getState().setSelectedSite("veupathdb");
    expect(useSessionStore.getState().strategyId).toBe("s-veu");
    useSessionStore.getState().setSelectedSite("toxodb");
    expect(useSessionStore.getState().strategyId).toBe("s-toxo");
  });

  it("setChatIsStreaming updates streaming state", () => {
    useSessionStore.getState().setChatIsStreaming(true);
    expect(useSessionStore.getState().chatIsStreaming).toBe(true);
  });

  it("bumpChatPreviewVersion increments monotonically", () => {
    const v0 = useSessionStore.getState().chatPreviewVersion;
    useSessionStore.getState().bumpChatPreviewVersion();
    expect(useSessionStore.getState().chatPreviewVersion).toBe(v0 + 1);
  });
});

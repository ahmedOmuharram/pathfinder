import { describe, expect, it, vi, afterEach } from "vitest";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetModules();
});

function makeLocalStorage(initial: Record<string, string> = {}) {
  const store = new Map<string, string>(Object.entries(initial));
  return {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
    removeItem: (k: string) => void store.delete(k),
  };
}

describe("state/useSessionStore", () => {
  it("reads initial auth token from localStorage when window exists", async () => {
    vi.stubGlobal("window", {
      localStorage: makeLocalStorage({ "pathfinder-auth-token": "t123" }),
    });

    const mod = await import("./useSessionStore");
    expect(mod.useSessionStore.getState().authToken).toBe("t123");
  });

  it("setAuthToken writes/removes localStorage when window exists", async () => {
    const localStorage = makeLocalStorage();
    vi.stubGlobal("window", { localStorage });

    const mod = await import("./useSessionStore");
    const store = mod.useSessionStore;

    store.getState().setAuthToken("abc");
    expect(localStorage.getItem("pathfinder-auth-token")).toBe("abc");

    store.getState().setAuthToken(null);
    expect(localStorage.getItem("pathfinder-auth-token")).toBeNull();
  });

  it("setSelectedSite updates selected site", async () => {
    const mod = await import("./useSessionStore");
    const store = mod.useSessionStore;
    store.getState().setSelectedSite("tri TrypDB");
    expect(store.getState().selectedSite).toBe("tri TrypDB");
  });

  it("setSelectedSiteInfo updates site and display name", async () => {
    const mod = await import("./useSessionStore");
    const store = mod.useSessionStore;
    store.getState().setSelectedSiteInfo("tri TrypDB", "TrypDB");
    expect(store.getState().selectedSite).toBe("tri TrypDB");
    expect(store.getState().selectedSiteDisplayName).toBe("TrypDB");
  });

  it("setStrategyId updates strategy id", async () => {
    const mod = await import("./useSessionStore");
    const store = mod.useSessionStore;
    store.getState().setStrategyId("s123");
    expect(store.getState().strategyId).toBe("s123");
    store.getState().setStrategyId(null);
    expect(store.getState().strategyId).toBeNull();
  });

  it("setPlanSessionId updates plan session id", async () => {
    const mod = await import("./useSessionStore");
    const store = mod.useSessionStore;
    store.getState().setPlanSessionId("p123");
    expect(store.getState().planSessionId).toBe("p123");
  });

  it("setVeupathdbAuth updates auth state", async () => {
    const mod = await import("./useSessionStore");
    const store = mod.useSessionStore;
    store.getState().setVeupathdbAuth(true, "John Doe");
    expect(store.getState().veupathdbSignedIn).toBe(true);
    expect(store.getState().veupathdbName).toBe("John Doe");
    store.getState().setVeupathdbAuth(false);
    expect(store.getState().veupathdbSignedIn).toBe(false);
    expect(store.getState().veupathdbName).toBeNull();
  });

  it("setChatIsStreaming updates streaming state", async () => {
    const mod = await import("./useSessionStore");
    const store = mod.useSessionStore;
    store.getState().setChatIsStreaming(true);
    expect(store.getState().chatIsStreaming).toBe(true);
  });

  it("linkConversation stores plan-to-strategy mapping and persists to localStorage", async () => {
    const localStorage = makeLocalStorage();
    vi.stubGlobal("window", { localStorage });

    const mod = await import("./useSessionStore");
    const store = mod.useSessionStore;
    store.getState().linkConversation("plan-1", "strategy-1");
    expect(store.getState().linkedConversations).toEqual({
      "plan-1": "strategy-1",
    });
    const persisted = JSON.parse(
      localStorage.getItem("pathfinder-linked-conversations") ?? "{}",
    );
    expect(persisted).toEqual({ "plan-1": "strategy-1" });
  });
});

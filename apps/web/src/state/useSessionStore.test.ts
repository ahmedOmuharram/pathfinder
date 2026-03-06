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

  it("changing selected site restores strategy for new site (null when none saved)", async () => {
    const mod = await import("./useSessionStore");
    const store = mod.useSessionStore;
    store.getState().setStrategyId("s1");
    store.getState().setSelectedSite("toxodb");
    expect(store.getState().selectedSite).toBe("toxodb");
    // No window in Node env, so restored strategy is null.
    expect(store.getState().strategyId).toBeNull();
  });

  it("setStrategyId updates strategy id", async () => {
    const mod = await import("./useSessionStore");
    const store = mod.useSessionStore;
    store.getState().setStrategyId("s123");
    expect(store.getState().strategyId).toBe("s123");
    store.getState().setStrategyId(null);
    expect(store.getState().strategyId).toBeNull();
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

  it("restores selectedSite from localStorage on init", async () => {
    vi.stubGlobal("window", {
      localStorage: makeLocalStorage({ "pathfinder-selected-site": "toxodb" }),
    });

    const mod = await import("./useSessionStore");
    expect(mod.useSessionStore.getState().selectedSite).toBe("toxodb");
  });

  it("restores strategyId scoped to site from localStorage on init", async () => {
    vi.stubGlobal("window", {
      localStorage: makeLocalStorage({
        "pathfinder-selected-site": "toxodb",
        "pathfinder-strategy-id:toxodb": "s-toxo-1",
      }),
    });

    const mod = await import("./useSessionStore");
    expect(mod.useSessionStore.getState().selectedSite).toBe("toxodb");
    expect(mod.useSessionStore.getState().strategyId).toBe("s-toxo-1");
  });

  it("setStrategyId persists to localStorage scoped by site", async () => {
    const localStorage = makeLocalStorage({
      "pathfinder-selected-site": "plasmodb",
    });
    vi.stubGlobal("window", { localStorage });

    const mod = await import("./useSessionStore");
    const store = mod.useSessionStore;

    store.getState().setStrategyId("s-new");
    expect(localStorage.getItem("pathfinder-strategy-id:plasmodb")).toBe("s-new");

    store.getState().setStrategyId(null);
    expect(localStorage.getItem("pathfinder-strategy-id:plasmodb")).toBeNull();
  });

  it("setSelectedSite persists to localStorage and restores strategy for new site", async () => {
    const localStorage = makeLocalStorage({
      "pathfinder-selected-site": "plasmodb",
      "pathfinder-strategy-id:plasmodb": "s-plasmo",
      "pathfinder-strategy-id:toxodb": "s-toxo",
    });
    vi.stubGlobal("window", { localStorage });

    const mod = await import("./useSessionStore");
    const store = mod.useSessionStore;

    // Switch to toxodb — should restore s-toxo
    store.getState().setSelectedSite("toxodb");
    expect(store.getState().selectedSite).toBe("toxodb");
    expect(store.getState().strategyId).toBe("s-toxo");
    expect(localStorage.getItem("pathfinder-selected-site")).toBe("toxodb");

    // Switch back to plasmodb — should restore s-plasmo
    store.getState().setSelectedSite("plasmodb");
    expect(store.getState().strategyId).toBe("s-plasmo");
  });

  it("restores selectedSiteDisplayName from localStorage", async () => {
    vi.stubGlobal("window", {
      localStorage: makeLocalStorage({
        "pathfinder-selected-site-display": "ToxoDB",
      }),
    });

    const mod = await import("./useSessionStore");
    expect(mod.useSessionStore.getState().selectedSiteDisplayName).toBe("ToxoDB");
  });
});

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
});

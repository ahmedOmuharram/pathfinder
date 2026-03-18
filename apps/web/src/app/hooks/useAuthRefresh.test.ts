/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockRefreshAuth = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api/veupathdb-auth", () => ({
  get refreshAuth() {
    return mockRefreshAuth;
  },
}));

let mockStoreState: {
  veupathdbSignedIn: boolean;
  authRefreshed: boolean;
};

const mockSetAuthRefreshed = vi.hoisted(() => vi.fn());
const mockBumpAuthVersion = vi.hoisted(() => vi.fn());

vi.mock("@/state/useSessionStore", () => ({
  useSessionStore: <T>(
    selector: (s: {
      veupathdbSignedIn: boolean;
      authRefreshed: boolean;
      setAuthRefreshed: (v: boolean) => void;
      bumpAuthVersion: () => void;
      selectedSite: string;
    }) => T,
  ) =>
    selector({
      veupathdbSignedIn: mockStoreState.veupathdbSignedIn,
      authRefreshed: mockStoreState.authRefreshed,
      setAuthRefreshed: mockSetAuthRefreshed,
      bumpAuthVersion: mockBumpAuthVersion,
      selectedSite: "plasmodb",
    }),
}));

describe("useAuthRefresh", () => {
  beforeEach(() => {
    mockStoreState = {
      veupathdbSignedIn: false,
      authRefreshed: false,
    };
    mockRefreshAuth.mockReset();
    mockSetAuthRefreshed.mockReset();
    mockBumpAuthVersion.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  async function importAndRender() {
    const { useAuthRefresh } = await import("./useAuthRefresh");
    return renderHook(() => useAuthRefresh());
  }

  it("does not refresh when user is not signed in", async () => {
    mockStoreState.veupathdbSignedIn = false;
    mockStoreState.authRefreshed = false;

    await importAndRender();

    expect(mockRefreshAuth).not.toHaveBeenCalled();
    expect(mockSetAuthRefreshed).not.toHaveBeenCalled();
  });

  it("does not refresh when already refreshed", async () => {
    mockStoreState.veupathdbSignedIn = true;
    mockStoreState.authRefreshed = true;

    await importAndRender();

    expect(mockRefreshAuth).not.toHaveBeenCalled();
  });

  it("refreshes auth when signed in and not yet refreshed", async () => {
    mockStoreState.veupathdbSignedIn = true;
    mockStoreState.authRefreshed = false;
    mockRefreshAuth.mockResolvedValueOnce({ success: true });

    await importAndRender();

    // Should eagerly mark as refreshed
    expect(mockSetAuthRefreshed).toHaveBeenCalledWith(true);
    expect(mockRefreshAuth).toHaveBeenCalledTimes(1);

    // Flush the promise chain
    await act(async () => {
      await Promise.resolve();
    });

    expect(mockBumpAuthVersion).toHaveBeenCalledTimes(1);
  });

  it("does not bump auth version on refresh failure", async () => {
    mockStoreState.veupathdbSignedIn = true;
    mockStoreState.authRefreshed = false;
    mockRefreshAuth.mockRejectedValueOnce(new Error("refresh failed"));

    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    await importAndRender();

    expect(mockSetAuthRefreshed).toHaveBeenCalledWith(true);
    expect(mockRefreshAuth).toHaveBeenCalledTimes(1);

    // Flush the rejected promise
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(mockBumpAuthVersion).not.toHaveBeenCalled();
    expect(consoleSpy).toHaveBeenCalledWith("[refreshAuth]", expect.any(Error));

    consoleSpy.mockRestore();
  });

  it("sets authRefreshed before awaiting the refresh call", async () => {
    mockStoreState.veupathdbSignedIn = true;
    mockStoreState.authRefreshed = false;

    // Track call order
    const callOrder: string[] = [];
    mockSetAuthRefreshed.mockImplementation(() => callOrder.push("setAuthRefreshed"));
    mockRefreshAuth.mockImplementation(() => {
      callOrder.push("refreshAuth");
      return Promise.resolve({ success: true });
    });

    await importAndRender();

    // setAuthRefreshed should be called before refreshAuth
    expect(callOrder[0]).toBe("setAuthRefreshed");
    expect(callOrder[1]).toBe("refreshAuth");
  });

  it("returns void (no return value)", async () => {
    mockStoreState.veupathdbSignedIn = false;
    const { result } = await importAndRender();

    expect(result.current).toBeUndefined();
  });
});

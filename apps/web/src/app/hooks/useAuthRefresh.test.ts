/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { createTestWrapper } from "@/lib/query/testing";

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
    const { Wrapper } = createTestWrapper();
    return renderHook(() => useAuthRefresh(), { wrapper: Wrapper });
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

    expect(mockRefreshAuth).toHaveBeenCalledTimes(1);

    // Flush the promise chain
    await act(async () => {
      await Promise.resolve();
    });

    // authRefreshed set AFTER successful refresh
    expect(mockSetAuthRefreshed).toHaveBeenCalledWith(true);
    expect(mockBumpAuthVersion).toHaveBeenCalledTimes(1);
  });

  it("does not bump auth version on refresh failure but still unblocks auth", async () => {
    mockStoreState.veupathdbSignedIn = true;
    mockStoreState.authRefreshed = false;
    mockRefreshAuth.mockRejectedValueOnce(new Error("refresh failed"));

    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    await importAndRender();

    expect(mockRefreshAuth).toHaveBeenCalledTimes(1);

    // Wait for TanStack Query to process the rejection and call throwOnError
    await waitFor(() => {
      expect(mockSetAuthRefreshed).toHaveBeenCalledWith(true);
    });

    expect(mockBumpAuthVersion).not.toHaveBeenCalled();

    consoleSpy.mockRestore();
  });

  it("sets authRefreshed after the refresh call succeeds", async () => {
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

    // Flush the promise chain
    await act(async () => {
      await Promise.resolve();
    });

    // refreshAuth should be called before setAuthRefreshed
    expect(callOrder[0]).toBe("refreshAuth");
    expect(callOrder[1]).toBe("setAuthRefreshed");
  });

  it("returns void (no return value)", async () => {
    mockStoreState.veupathdbSignedIn = false;
    const { result } = await importAndRender();

    expect(result.current).toBeUndefined();
  });
});

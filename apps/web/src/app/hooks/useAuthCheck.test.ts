/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockGetVeupathdbAuthStatus = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api/veupathdb-auth", () => ({
  get getVeupathdbAuthStatus() {
    return mockGetVeupathdbAuthStatus;
  },
}));

// Mock the session store with controllable state.
// The hook reads four selectors: authStatusKnown, setVeupathdbAuth,
// setAuthStatusKnown (from the store) and manages apiError locally.
let mockAuthStatusKnown: boolean;

const mockSetVeupathdbAuth = vi.hoisted(() => vi.fn());
const mockSetAuthStatusKnown = vi.hoisted(() => vi.fn());

vi.mock("@/state/useSessionStore", () => ({
  useSessionStore: <T>(
    selector: (s: {
      authStatusKnown: boolean;
      setVeupathdbAuth: (signedIn: boolean, name?: string | null) => void;
      setAuthStatusKnown: (value: boolean) => void;
      selectedSite: string;
    }) => T,
  ) =>
    selector({
      authStatusKnown: mockAuthStatusKnown,
      setVeupathdbAuth: mockSetVeupathdbAuth,
      setAuthStatusKnown: mockSetAuthStatusKnown,
      selectedSite: "plasmodb",
    }),
}));

describe("useAuthCheck", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockAuthStatusKnown = false;
    // Default: return a never-resolving promise so nothing blows up
    mockGetVeupathdbAuthStatus.mockReset().mockReturnValue(new Promise(() => {}));
    mockSetVeupathdbAuth.mockReset();
    mockSetAuthStatusKnown.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  async function importAndRender() {
    const { useAuthCheck } = await import("./useAuthCheck");
    return renderHook(() => useAuthCheck());
  }

  // ---------------------------------------------------------------------------
  // Initial state
  // ---------------------------------------------------------------------------

  it("returns authLoading=true and apiError=null initially", async () => {
    const { result } = await importAndRender();

    expect(result.current.authLoading).toBe(true);
    expect(result.current.apiError).toBeNull();
  });

  it("returns authLoading=false when authStatusKnown is true", async () => {
    mockAuthStatusKnown = true;
    const { result } = await importAndRender();

    expect(result.current.authLoading).toBe(false);
  });

  // ---------------------------------------------------------------------------
  // Success path
  // ---------------------------------------------------------------------------

  it("calls getVeupathdbAuthStatus and sets auth on success", async () => {
    mockGetVeupathdbAuthStatus.mockResolvedValue({
      signedIn: true,
      name: "Test User",
      email: "test@example.com",
    });

    await importAndRender();

    // Flush the setTimeout(fn, 0) in the effect
    await act(async () => {
      vi.advanceTimersByTime(1);
    });

    // Flush the resolved promise
    await act(async () => {
      await vi.runAllTimersAsync();
    });

    expect(mockGetVeupathdbAuthStatus).toHaveBeenCalled();
    expect(mockSetVeupathdbAuth).toHaveBeenCalledWith(true, "Test User");
    expect(mockSetAuthStatusKnown).toHaveBeenCalledWith(true);
  });

  it("handles null name in auth status", async () => {
    mockGetVeupathdbAuthStatus.mockResolvedValue({
      signedIn: false,
      name: null,
      email: null,
    });

    await importAndRender();

    await act(async () => {
      vi.advanceTimersByTime(1);
    });

    await act(async () => {
      await vi.runAllTimersAsync();
    });

    expect(mockSetVeupathdbAuth).toHaveBeenCalledWith(false, null);
  });

  // ---------------------------------------------------------------------------
  // Error paths
  // ---------------------------------------------------------------------------

  it("sets apiError on fetch failure with Error message", async () => {
    mockGetVeupathdbAuthStatus.mockRejectedValue(new Error("Network failure"));

    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const { result } = await importAndRender();

    await act(async () => {
      vi.advanceTimersByTime(1);
    });

    await act(async () => {
      await vi.runAllTimersAsync();
    });

    expect(result.current.apiError).toBe("Network failure");
    expect(mockSetAuthStatusKnown).toHaveBeenCalledWith(true);
    consoleSpy.mockRestore();
  });

  it("sets fallback apiError message for non-Error rejections", async () => {
    mockGetVeupathdbAuthStatus.mockRejectedValue("string error");

    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const { result } = await importAndRender();

    await act(async () => {
      vi.advanceTimersByTime(1);
    });

    await act(async () => {
      await vi.runAllTimersAsync();
    });

    expect(result.current.apiError).toBe("Unable to reach the API.");
    consoleSpy.mockRestore();
  });

  // ---------------------------------------------------------------------------
  // Skip logic
  // ---------------------------------------------------------------------------

  it("does not run check when authStatusKnown is true and no apiError", async () => {
    mockAuthStatusKnown = true;

    await importAndRender();

    await act(async () => {
      vi.advanceTimersByTime(10);
    });

    // The default mock returns a pending promise, so if the hook called it
    // we would see a call.  authStatusKnown=true + apiError=null should skip.
    expect(mockGetVeupathdbAuthStatus).not.toHaveBeenCalled();
  });

  // ---------------------------------------------------------------------------
  // Retry
  // ---------------------------------------------------------------------------

  it("retry clears apiError and resets authStatusKnown", async () => {
    mockGetVeupathdbAuthStatus.mockRejectedValue(new Error("fail"));

    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const { result } = await importAndRender();

    await act(async () => {
      vi.advanceTimersByTime(1);
    });

    await act(async () => {
      await vi.runAllTimersAsync();
    });

    expect(result.current.apiError).toBe("fail");

    // Call retry
    act(() => result.current.retry());

    // retry should clear apiError locally and reset authStatusKnown in the store
    expect(result.current.apiError).toBeNull();
    expect(mockSetAuthStatusKnown).toHaveBeenCalledWith(false);
    consoleSpy.mockRestore();
  });

  // ---------------------------------------------------------------------------
  // Callback stability
  // ---------------------------------------------------------------------------

  it("exposes retry as a stable function", async () => {
    const { result, rerender } = await importAndRender();

    const firstRetry = result.current.retry;

    await act(async () => {
      rerender();
    });

    expect(result.current.retry).toBe(firstRetry);
  });
});

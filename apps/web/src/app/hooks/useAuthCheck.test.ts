/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { createSuspenseWrapper } from "@/lib/query/testing";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockGetVeupathdbAuthStatus = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api/veupathdb-auth", () => ({
  authStatusOptions: (siteId: string) => ({
    queryKey: ["auth", "status", siteId],
    queryFn: () => mockGetVeupathdbAuthStatus(siteId),
  }),
}));

const mockSetVeupathdbAuth = vi.hoisted(() => vi.fn());
const mockSetAuthStatusKnown = vi.hoisted(() => vi.fn());
const mockBumpAuthVersion = vi.hoisted(() => vi.fn());
const mockInvalidateUserScopedQueries = vi.hoisted(() => vi.fn());

vi.mock("@/lib/query/invalidateUserScoped", () => ({
  invalidateUserScopedQueries: mockInvalidateUserScopedQueries,
}));

vi.mock("@/state/useSessionStore", () => ({
  useSessionStore: <T>(
    selector: (s: {
      setVeupathdbAuth: (signedIn: boolean, name: string | null) => void;
      setAuthStatusKnown: (value: boolean) => void;
      selectedSite: string;
      bumpAuthVersion: () => void;
    }) => T,
  ) =>
    selector({
      setVeupathdbAuth: mockSetVeupathdbAuth,
      setAuthStatusKnown: mockSetAuthStatusKnown,
      selectedSite: "plasmodb",
      bumpAuthVersion: mockBumpAuthVersion,
    }),
}));

describe("useAuthCheck", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockGetVeupathdbAuthStatus.mockReset();
    mockSetVeupathdbAuth.mockReset();
    mockSetAuthStatusKnown.mockReset();
    mockBumpAuthVersion.mockReset();
    mockInvalidateUserScopedQueries.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  async function importAndRender() {
    const { useAuthCheck } = await import("./useAuthCheck");
    const { Wrapper } = createSuspenseWrapper();
    return renderHook(() => useAuthCheck(), { wrapper: Wrapper });
  }

  // ---------------------------------------------------------------------------
  // Success path
  // ---------------------------------------------------------------------------

  it("calls getVeupathdbAuthStatus and syncs auth state to store on success", async () => {
    mockGetVeupathdbAuthStatus.mockResolvedValue({
      signedIn: true,
      name: "Test User",
      email: "test@example.com",
    });

    await importAndRender();

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
      await vi.runAllTimersAsync();
    });

    expect(mockSetVeupathdbAuth).toHaveBeenCalledWith(false, null);
  });

  // ---------------------------------------------------------------------------
  // Auth transition invalidation
  // ---------------------------------------------------------------------------

  it("does NOT invalidate on initial mount (no prior state to transition from)", async () => {
    mockGetVeupathdbAuthStatus.mockResolvedValue({
      signedIn: true,
      name: "Test User",
    });

    await importAndRender();

    await act(async () => {
      await vi.runAllTimersAsync();
    });

    // prev === null on the first check, so no invalidation should happen
    expect(mockInvalidateUserScopedQueries).not.toHaveBeenCalled();
    expect(mockBumpAuthVersion).not.toHaveBeenCalled();
  });

  it("does NOT invalidate when signed-in state is stable across re-renders", async () => {
    mockGetVeupathdbAuthStatus.mockResolvedValue({
      signedIn: true,
      name: "Test User",
    });

    const { rerender } = await importAndRender();

    await act(async () => {
      await vi.runAllTimersAsync();
    });

    await act(async () => {
      rerender();
      await vi.runAllTimersAsync();
    });

    expect(mockInvalidateUserScopedQueries).not.toHaveBeenCalled();
    expect(mockBumpAuthVersion).not.toHaveBeenCalled();
  });
});

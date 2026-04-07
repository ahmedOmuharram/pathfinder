/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { createTestWrapper } from "@/lib/query/testing";
import { APIError } from "@/lib/api/http";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockGetSystemConfig = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api/health", () => ({
  getSystemConfig: mockGetSystemConfig,
  systemConfigOptions: () => ({
    queryKey: ["config", "system"] as const,
    queryFn: mockGetSystemConfig,
    staleTime: Infinity,
  }),
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** A fully-populated SystemConfigResponse matching the real Zod schema. */
function makeConfigResponse(overrides: { llmConfigured: boolean }) {
  return {
    chatProvider: "anthropic",
    llmConfigured: overrides.llmConfigured,
    providers: {
      openai: false,
      anthropic: overrides.llmConfigured,
      google: false,
      ollama: false,
    },
  };
}

async function importAndRender() {
  const { useSystemConfig } = await import("./useSystemConfig");
  const { Wrapper } = createTestWrapper();
  return renderHook(() => useSystemConfig(), { wrapper: Wrapper });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useSystemConfig", () => {
  beforeEach(() => {
    vi.resetModules();
    mockGetSystemConfig.mockReset();
  });

  it("returns configLoading=true and setupRequired=false initially", async () => {
    // Never-resolving promise keeps the query in pending state.
    mockGetSystemConfig.mockReturnValue(new Promise(() => {}));

    const { result } = await importAndRender();

    expect(result.current.configLoading).toBe(true);
    expect(result.current.setupRequired).toBe(false);
  });

  it("returns setupRequired=false when LLM is configured", async () => {
    mockGetSystemConfig.mockResolvedValue(makeConfigResponse({ llmConfigured: true }));

    const { result } = await importAndRender();

    await waitFor(() => {
      expect(result.current.configLoading).toBe(false);
    });

    expect(result.current.setupRequired).toBe(false);
  });

  it("returns setupRequired=true when LLM is NOT configured", async () => {
    mockGetSystemConfig.mockResolvedValue(makeConfigResponse({ llmConfigured: false }));

    const { result } = await importAndRender();

    await waitFor(() => {
      expect(result.current.configLoading).toBe(false);
    });

    expect(result.current.setupRequired).toBe(true);
  });

  it("handles network failure gracefully — setupRequired stays false", async () => {
    mockGetSystemConfig.mockRejectedValue(
      new APIError("Service Unavailable", {
        status: 503,
        statusText: "Service Unavailable",
        url: "http://localhost:8000/health/config",
        data: null,
      }),
    );

    const { result } = await importAndRender();

    await waitFor(() => {
      expect(result.current.configLoading).toBe(false);
    });

    // On error, data is undefined so `data?.llmConfigured === false` is false.
    expect(result.current.setupRequired).toBe(false);
  });

  it("retry() triggers a new fetch after initial failure", async () => {
    // First call rejects, second call succeeds.
    mockGetSystemConfig
      .mockRejectedValueOnce(
        new APIError("Service Unavailable", {
          status: 503,
          statusText: "Service Unavailable",
          url: "http://localhost:8000/health/config",
          data: null,
        }),
      )
      .mockResolvedValueOnce(makeConfigResponse({ llmConfigured: true }));

    const { result } = await importAndRender();

    // Wait for the first (failed) attempt to settle.
    await waitFor(() => {
      expect(result.current.configLoading).toBe(false);
    });

    expect(result.current.setupRequired).toBe(false);
    expect(mockGetSystemConfig).toHaveBeenCalledTimes(1);

    // Trigger retry — refetches with the second mock value.
    result.current.retry();

    await waitFor(() => {
      expect(mockGetSystemConfig).toHaveBeenCalledTimes(2);
    });

    await waitFor(() => {
      expect(result.current.configLoading).toBe(false);
    });

    expect(result.current.setupRequired).toBe(false);
  });
});

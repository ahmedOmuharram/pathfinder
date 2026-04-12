/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { createTestWrapper } from "@/lib/query/testing";
import type { Strategy } from "@pathfinder/shared";

const mockOpenStrategy = vi.hoisted(() => vi.fn());
const mockSetStrategyId = vi.hoisted(() => vi.fn());
const mockBumpChatPreviewVersion = vi.hoisted(() => vi.fn());

let mockStrategyId: string | null = null;
let mockSignedIn = true;
let mockChatIsStreaming = false;

vi.mock("@/lib/api/strategies", () => ({
  openStrategy: mockOpenStrategy,
  strategiesListOptions: (siteId: string) => ({
    queryKey: ["strategies", "list", siteId] as const,
    queryFn: vi.fn(),
  }),
}));

vi.mock("@/state/useSessionStore", () => {
  const useSessionStore = <T>(
    selector: (s: {
      strategyId: string | null;
      setStrategyId: (id: string | null) => void;
      bumpChatPreviewVersion: () => void;
      veupathdbSignedIn: boolean;
      chatIsStreaming: boolean;
    }) => T,
  ) =>
    selector({
      strategyId: mockStrategyId,
      setStrategyId: mockSetStrategyId,
      bumpChatPreviewVersion: mockBumpChatPreviewVersion,
      veupathdbSignedIn: mockSignedIn,
      chatIsStreaming: mockChatIsStreaming,
    });

  useSessionStore.getState = () => ({
    strategyId: mockStrategyId,
    setStrategyId: mockSetStrategyId,
    bumpChatPreviewVersion: mockBumpChatPreviewVersion,
    veupathdbSignedIn: mockSignedIn,
    chatIsStreaming: mockChatIsStreaming,
  });

  return { useSessionStore };
});

import { useAutoConversation } from "./useAutoConversation";

function makeStrategy(id: string): Strategy {
  return {
    id,
    name: `Strategy ${id}`,
    siteId: "plasmodb",
    recordType: "transcript",
    steps: [],
    rootStepId: null,
    stepCount: 0,
    isSaved: false,
    createdAt: "2026-01-15T12:00:00.000Z",
    updatedAt: "2026-01-15T12:00:00.000Z",
  };
}

describe("useAutoConversation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockStrategyId = null;
    mockSignedIn = true;
    mockChatIsStreaming = false;
  });

  it("bumps the chat preview before auto-picking a conversation", async () => {
    const { Wrapper } = createTestWrapper();

    renderHook(
      () =>
        useAutoConversation({
          siteId: "plasmodb",
          strategyItems: [makeStrategy("picked-1")],
          isFetched: true,
        }),
      { wrapper: Wrapper },
    );

    await waitFor(() => {
      expect(mockBumpChatPreviewVersion).toHaveBeenCalledTimes(1);
    });
    expect(mockSetStrategyId).toHaveBeenCalledWith("picked-1");
  });

  it("bumps the chat preview before auto-creating a conversation", async () => {
    const { Wrapper } = createTestWrapper();
    mockOpenStrategy.mockResolvedValueOnce({ strategyId: "new-auto-1" });

    renderHook(
      () =>
        useAutoConversation({
          siteId: "plasmodb",
          strategyItems: [],
          isFetched: true,
        }),
      { wrapper: Wrapper },
    );

    await waitFor(() => {
      expect(mockOpenStrategy).toHaveBeenCalledTimes(1);
    });

    expect(mockBumpChatPreviewVersion).toHaveBeenCalledTimes(1);
    expect(mockSetStrategyId).toHaveBeenCalledWith("new-auto-1");
  });
});

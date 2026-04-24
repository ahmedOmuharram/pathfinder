/**
 * @vitest-environment jsdom
 */

import type * as ConversationsModule from "@/lib/api/conversations";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { Strategy } from "@pathfinder/shared";

const pushConversationMock = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api/conversations", async (importOriginal) => {
  const actual =
    await importOriginal<typeof ConversationsModule>();
  return { ...actual, pushConversation: pushConversationMock };
});

const toastErrorMock = vi.hoisted(() => vi.fn());
const toastWarningMock = vi.hoisted(() => vi.fn());
vi.mock("sonner", () => ({
  toast: { error: toastErrorMock, warning: toastWarningMock, success: vi.fn() },
}));

import { useStrategyStore } from "@/state/strategy/store";
import { usePushStrategyMutation } from "./usePushStrategyMutation";
import { makeQueryHarness } from "./__tests__/strategyTestUtils";

function makeStrategy(overrides: Partial<Strategy> = {}): Strategy {
  return {
    id: "strategy-1",
    name: "Test Strategy",
    siteId: "plasmodb",
    recordType: "gene",
    steps: [
      {
        id: "s1",
        displayName: "Genes by taxon",
        searchName: "GenesByTaxon",
        recordType: "gene",
        parameters: { organism: "Plasmodium" },
        isBuilt: false,
        isFiltered: false,
      },
    ],
    rootStepId: "s1",
    isSaved: false,
    description: null,
    wdkStrategyId: null,
    wdkUrl: null,
    createdAt: "2026-01-01T00:00:00.000Z",
    updatedAt: "2026-01-01T00:00:00.000Z",
    ...overrides,
  };
}

beforeEach(() => {
  useStrategyStore.getState().clear();
  useStrategyStore.setState({ graphValidationStatus: {} });
  pushConversationMock.mockReset();
  toastErrorMock.mockReset();
  toastWarningMock.mockReset();
});

describe("usePushStrategyMutation", () => {
  it("applies optimistic update synchronously and replaces with server response", async () => {
    const initial = makeStrategy();
    const harness = makeQueryHarness(initial);

    const optimistic = makeStrategy({
      steps: [
        {
          ...initial.steps[0]!,
          displayName: "Renamed locally",
        },
      ],
    });

    const serverResponse = makeStrategy({
      wdkStrategyId: 99,
      wdkUrl: "http://example.com",
      steps: [
        {
          ...initial.steps[0]!,
          displayName: "Renamed locally (server canonical)",
        },
      ],
    });
    pushConversationMock.mockResolvedValueOnce(serverResponse);

    const { result } = renderHook(() => usePushStrategyMutation(), {
      wrapper: harness.wrapper,
    });

    let mutationPromise: Promise<unknown> | undefined;
    act(() => {
      mutationPromise = result.current.mutateAsync({ optimistic });
    });

    expect(harness.getStrategy(initial.id)?.steps[0]?.displayName).toBe(
      "Renamed locally",
    );

    await act(async () => {
      await mutationPromise;
    });

    await waitFor(() => {
      expect(harness.getStrategy(initial.id)?.steps[0]?.displayName).toBe(
        "Renamed locally (server canonical)",
      );
      expect(harness.getStrategy(initial.id)?.wdkStrategyId).toBe(99);
    });
  });

  it("rolls back to previous strategy on error and shows toast", async () => {
    const initial = makeStrategy();
    const harness = makeQueryHarness(initial);

    const optimistic = makeStrategy({
      steps: [
        {
          ...initial.steps[0]!,
          displayName: "Will fail",
        },
      ],
    });

    pushConversationMock.mockRejectedValueOnce(new Error("Network broke"));

    const { result } = renderHook(() => usePushStrategyMutation(), {
      wrapper: harness.wrapper,
    });

    await act(async () => {
      await expect(
        result.current.mutateAsync({ optimistic }),
      ).rejects.toThrow("Network broke");
    });

    await waitFor(() => {
      expect(harness.getStrategy(initial.id)?.steps[0]?.displayName).toBe(
        "Genes by taxon",
      );
    });
    expect(toastErrorMock).toHaveBeenCalled();
  });

  it("refuses to fire when graphValidationStatus[id] === true", async () => {
    const initial = makeStrategy();
    const harness = makeQueryHarness(initial);
    useStrategyStore.getState().setGraphValidationStatus(initial.id, true);

    const optimistic = makeStrategy({
      steps: [
        {
          ...initial.steps[0]!,
          displayName: "Should not push",
        },
      ],
    });

    const { result } = renderHook(() => usePushStrategyMutation(), {
      wrapper: harness.wrapper,
    });

    await act(async () => {
      await expect(
        result.current.mutateAsync({ optimistic }),
      ).rejects.toThrow();
    });

    expect(pushConversationMock).not.toHaveBeenCalled();
    expect(harness.getStrategy(initial.id)?.steps[0]?.displayName).toBe(
      "Genes by taxon",
    );
    expect(toastWarningMock).toHaveBeenCalledWith(
      expect.stringMatching(/Sync paused/i),
    );
  });

  it("scope.id serializes concurrent pushes — B's mutationFn waits for A", async () => {
    const initial = makeStrategy();
    const harness = makeQueryHarness(initial);

    const optimisticA = makeStrategy({
      steps: [{ ...initial.steps[0]!, displayName: "A optimistic" }],
    });
    const optimisticB = makeStrategy({
      steps: [{ ...initial.steps[0]!, displayName: "B optimistic" }],
    });
    const serverA = makeStrategy({
      steps: [{ ...initial.steps[0]!, displayName: "A server" }],
    });
    const serverB = makeStrategy({
      steps: [{ ...initial.steps[0]!, displayName: "B server" }],
    });

    let resolveA!: (s: Strategy) => void;
    let resolveB!: (s: Strategy) => void;
    pushConversationMock.mockReturnValueOnce(
      new Promise<Strategy>((r) => {
        resolveA = r;
      }),
    );
    pushConversationMock.mockReturnValueOnce(
      new Promise<Strategy>((r) => {
        resolveB = r;
      }),
    );

    const { result } = renderHook(() => usePushStrategyMutation(), {
      wrapper: harness.wrapper,
    });

    act(() => {
      void result.current.mutateAsync({ optimistic: optimisticA });
    });
    await waitFor(() => {
      expect(pushConversationMock).toHaveBeenCalledTimes(1);
    });

    act(() => {
      void result.current.mutateAsync({ optimistic: optimisticB });
    });
    expect(pushConversationMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveA(serverA);
      await new Promise((r) => setTimeout(r, 0));
    });

    await waitFor(() => {
      expect(pushConversationMock).toHaveBeenCalledTimes(2);
    });

    await act(async () => {
      resolveB(serverB);
      await new Promise((r) => setTimeout(r, 0));
    });

    await waitFor(() => {
      expect(harness.getStrategy(initial.id)?.steps[0]?.displayName).toBe(
        "B server",
      );
    });
  });
});

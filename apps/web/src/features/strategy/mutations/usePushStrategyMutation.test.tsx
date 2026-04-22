/**
 * @vitest-environment jsdom
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { Strategy } from "@pathfinder/shared";

const pushConversationMock = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api/conversations", () => ({
  pushConversation: pushConversationMock,
}));

const toastErrorMock = vi.hoisted(() => vi.fn());
const toastWarningMock = vi.hoisted(() => vi.fn());
vi.mock("sonner", () => ({
  toast: { error: toastErrorMock, warning: toastWarningMock, success: vi.fn() },
}));

import { useStrategyStore } from "@/state/strategy/store";
import { usePushStrategyMutation } from "./usePushStrategyMutation";

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
    useStrategyStore.getState().setStrategy(initial);

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

    const { result } = renderHook(() => usePushStrategyMutation());

    let mutationPromise: Promise<unknown> | undefined;
    act(() => {
      mutationPromise = result.current.mutateAsync({ optimistic });
    });

    expect(useStrategyStore.getState().strategy?.steps[0]?.displayName).toBe(
      "Renamed locally",
    );

    await act(async () => {
      await mutationPromise;
    });

    await waitFor(() => {
      expect(useStrategyStore.getState().strategy?.steps[0]?.displayName).toBe(
        "Renamed locally (server canonical)",
      );
      expect(useStrategyStore.getState().strategy?.wdkStrategyId).toBe(99);
    });
  });

  it("rolls back to previous strategy on error and shows toast", async () => {
    const initial = makeStrategy();
    useStrategyStore.getState().setStrategy(initial);

    const optimistic = makeStrategy({
      steps: [
        {
          ...initial.steps[0]!,
          displayName: "Will fail",
        },
      ],
    });

    pushConversationMock.mockRejectedValueOnce(new Error("Network broke"));

    const { result } = renderHook(() => usePushStrategyMutation());

    await act(async () => {
      await expect(
        result.current.mutateAsync({ optimistic }),
      ).rejects.toThrow("Network broke");
    });

    await waitFor(() => {
      expect(useStrategyStore.getState().strategy?.steps[0]?.displayName).toBe(
        "Genes by taxon",
      );
    });
    expect(toastErrorMock).toHaveBeenCalled();
  });

  it("refuses to fire when graphValidationStatus[id] === true", async () => {
    const initial = makeStrategy();
    useStrategyStore.getState().setStrategy(initial);
    useStrategyStore.getState().setGraphValidationStatus(initial.id, true);

    const optimistic = makeStrategy({
      steps: [
        {
          ...initial.steps[0]!,
          displayName: "Should not push",
        },
      ],
    });

    const { result } = renderHook(() => usePushStrategyMutation());

    await act(async () => {
      await expect(
        result.current.mutateAsync({ optimistic }),
      ).rejects.toThrow();
    });

    expect(pushConversationMock).not.toHaveBeenCalled();
    expect(useStrategyStore.getState().strategy?.steps[0]?.displayName).toBe(
      "Genes by taxon",
    );
    expect(toastWarningMock).toHaveBeenCalledWith(
      expect.stringMatching(/Sync paused/i),
    );
  });

  it("guards against duplicate concurrent pushes with isPending", async () => {
    const initial = makeStrategy();
    useStrategyStore.getState().setStrategy(initial);

    const optimistic = makeStrategy();
    let resolveFn!: (s: Strategy) => void;
    pushConversationMock.mockReturnValueOnce(
      new Promise<Strategy>((resolve) => {
        resolveFn = resolve;
      }),
    );

    const { result } = renderHook(() => usePushStrategyMutation());

    let firstPromise: Promise<unknown> | undefined;
    act(() => {
      firstPromise = result.current.mutateAsync({ optimistic });
    });
    await waitFor(() => expect(result.current.isPending).toBe(true));

    await act(async () => {
      resolveFn(initial);
      await firstPromise;
    });

    expect(pushConversationMock).toHaveBeenCalledTimes(1);
  });
});

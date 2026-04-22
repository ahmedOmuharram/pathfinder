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
vi.mock("sonner", () => ({
  toast: {
    error: toastErrorMock,
    warning: vi.fn(),
    success: vi.fn(),
  },
}));

import { useStrategyStore } from "@/state/strategy/store";
import { useRetryLastPush } from "./useRetryLastPush";
import { usePushStrategyMutation } from "./usePushStrategyMutation";

function makeStrategy(name = "Test"): Strategy {
  return {
    id: "strategy-1",
    name,
    siteId: "plasmodb",
    recordType: "gene",
    steps: [
      {
        id: "s1",
        displayName: "Genes by taxon",
        searchName: "GenesByTaxon",
        recordType: "gene",
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
  };
}

beforeEach(() => {
  useStrategyStore.getState().clear();
  useStrategyStore.setState({ graphValidationStatus: {} });
  pushConversationMock.mockReset();
  toastErrorMock.mockReset();
});

describe("useRetryLastPush", () => {
  it("does nothing when lastFailedPush is null", async () => {
    const { result } = renderHook(() => useRetryLastPush());

    await act(async () => {
      result.current();
    });

    expect(pushConversationMock).not.toHaveBeenCalled();
  });

  it("re-fires the most recent failed push and clears lastFailedPush on success", async () => {
    const initial = makeStrategy("Failing");
    useStrategyStore.getState().setStrategy(initial);

    pushConversationMock
      .mockRejectedValueOnce(new Error("transient"))
      .mockResolvedValueOnce(initial);

    const { result } = renderHook(() => {
      const retry = useRetryLastPush();
      const push = usePushStrategyMutation();
      return { retry, push };
    });

    await act(async () => {
      await expect(
        result.current.push.mutateAsync({ optimistic: initial }),
      ).rejects.toThrow("transient");
    });

    await waitFor(() => {
      expect(useStrategyStore.getState().lastFailedPush).not.toBeNull();
    });

    await act(async () => {
      result.current.retry();
    });

    await waitFor(() => {
      expect(pushConversationMock).toHaveBeenCalledTimes(2);
      expect(useStrategyStore.getState().lastFailedPush).toBeNull();
    });
  });
});

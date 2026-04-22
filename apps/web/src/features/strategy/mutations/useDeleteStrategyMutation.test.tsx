/**
 * @vitest-environment jsdom
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { Strategy } from "@pathfinder/shared";

const deleteConversationMock = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api/conversations", () => ({
  deleteConversation: deleteConversationMock,
}));

const toastErrorMock = vi.hoisted(() => vi.fn());
const toastSuccessMock = vi.hoisted(() => vi.fn());
vi.mock("sonner", () => ({
  toast: {
    error: toastErrorMock,
    warning: vi.fn(),
    success: toastSuccessMock,
  },
}));

const routerPushMock = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: routerPushMock,
    replace: vi.fn(),
    back: vi.fn(),
  }),
}));

import { useStrategyStore } from "@/state/strategy/store";
import { createTestWrapper } from "@/lib/query/testing";
import { useDeleteStrategyMutation } from "./useDeleteStrategyMutation";

function makeStrategy(): Strategy {
  return {
    id: "strategy-1",
    name: "My strategy",
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
  deleteConversationMock.mockReset();
  toastErrorMock.mockReset();
  toastSuccessMock.mockReset();
  routerPushMock.mockReset();
});

describe("useDeleteStrategyMutation", () => {
  it("calls DELETE endpoint, clears store, navigates, and toasts success", async () => {
    const initial = makeStrategy();
    useStrategyStore.getState().setStrategy(initial);
    deleteConversationMock.mockResolvedValueOnce(undefined);

    const { Wrapper } = createTestWrapper();
    const { result } = renderHook(() => useDeleteStrategyMutation(), {
      wrapper: Wrapper,
    });

    await act(async () => {
      await result.current.mutateAsync({
        conversationId: "strategy-1",
        siteId: "plasmodb",
      });
    });

    expect(deleteConversationMock).toHaveBeenCalledWith("strategy-1");
    expect(useStrategyStore.getState().strategy).toBeNull();
    expect(routerPushMock).toHaveBeenCalledWith("/plasmodb/conversation");
    expect(toastSuccessMock).toHaveBeenCalled();
  });

  it("does NOT clear store or navigate on error and toasts the error", async () => {
    const initial = makeStrategy();
    useStrategyStore.getState().setStrategy(initial);
    deleteConversationMock.mockRejectedValueOnce(new Error("Boom"));

    const { Wrapper } = createTestWrapper();
    const { result } = renderHook(() => useDeleteStrategyMutation(), {
      wrapper: Wrapper,
    });

    await act(async () => {
      await expect(
        result.current.mutateAsync({
          conversationId: "strategy-1",
          siteId: "plasmodb",
        }),
      ).rejects.toThrow("Boom");
    });

    expect(useStrategyStore.getState().strategy?.id).toBe("strategy-1");
    expect(routerPushMock).not.toHaveBeenCalled();
    await waitFor(() => {
      expect(toastErrorMock).toHaveBeenCalled();
    });
  });
});

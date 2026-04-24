/**
 * @vitest-environment jsdom
 */

import type * as ConversationsModule from "@/lib/api/conversations";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { Strategy } from "@pathfinder/shared";

const deleteConversationMock = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api/conversations", async (importOriginal) => {
  const actual =
    await importOriginal<typeof ConversationsModule>();
  return { ...actual, deleteConversation: deleteConversationMock };
});

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
import { useDeleteStrategyMutation } from "./useDeleteStrategyMutation";
import { makeQueryHarness } from "./__tests__/strategyTestUtils";

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
  it("calls DELETE endpoint, removes the cache entry, navigates, and toasts success", async () => {
    const initial = makeStrategy();
    const harness = makeQueryHarness(initial);
    deleteConversationMock.mockResolvedValueOnce(undefined);

    const { result } = renderHook(() => useDeleteStrategyMutation(), {
      wrapper: harness.wrapper,
    });

    await act(async () => {
      await result.current.mutateAsync({
        conversationId: initial.id,
        siteId: "plasmodb",
      });
    });

    expect(deleteConversationMock).toHaveBeenCalledWith(initial.id);
    expect(harness.getStrategy(initial.id)).toBeNull();
    expect(routerPushMock).toHaveBeenCalledWith("/plasmodb/conversation");
    expect(toastSuccessMock).toHaveBeenCalled();
  });

  it("does NOT remove cache entry or navigate on error, toasts the error", async () => {
    const initial = makeStrategy();
    const harness = makeQueryHarness(initial);
    deleteConversationMock.mockRejectedValueOnce(new Error("Boom"));

    const { result } = renderHook(() => useDeleteStrategyMutation(), {
      wrapper: harness.wrapper,
    });

    await act(async () => {
      await expect(
        result.current.mutateAsync({
          conversationId: initial.id,
          siteId: "plasmodb",
        }),
      ).rejects.toThrow("Boom");
    });

    expect(harness.getStrategy(initial.id)?.id).toBe("strategy-1");
    expect(routerPushMock).not.toHaveBeenCalled();
    await waitFor(() => {
      expect(toastErrorMock).toHaveBeenCalled();
    });
  });
});

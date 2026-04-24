/**
 * @vitest-environment jsdom
 */

import type * as ConversationsModule from "@/lib/api/conversations";
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Strategy } from "@pathfinder/shared";

const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, replace: vi.fn(), back: vi.fn() }),
}));

const pushConversationMock = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api/conversations", async (importOriginal) => {
  const actual =
    await importOriginal<typeof ConversationsModule>();
  return { ...actual, pushConversation: pushConversationMock };
});

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), warning: vi.fn(), success: vi.fn() },
}));

import { useStrategyStore } from "@/state/strategy/store";
import { usePushStrategyMutation } from "@/features/strategy/mutations/usePushStrategyMutation";
import { makeQueryHarness } from "@/features/strategy/mutations/__tests__/strategyTestUtils";
import { useFlushBeforeNav } from "./useFlushBeforeNav";

function makeStrategy(): Strategy {
  return {
    id: "s",
    name: "S",
    siteId: "plasmodb",
    recordType: "gene",
    steps: [
      {
        id: "x",
        displayName: "X",
        searchName: "geneById",
        recordType: "gene",
        isBuilt: false,
        isFiltered: false,
      },
    ],
    rootStepId: "x",
    isSaved: false,
    description: null,
    wdkStrategyId: null,
    wdkUrl: null,
    createdAt: "t",
    updatedAt: "t",
  };
}

beforeEach(() => {
  pushMock.mockReset();
  pushConversationMock.mockReset();
  useStrategyStore.getState().clear();
  useStrategyStore.setState({ graphValidationStatus: {} });
});

describe("useFlushBeforeNav", () => {
  it("navigates immediately when no mutation is pending", async () => {
    const harness = makeQueryHarness();
    const { result } = renderHook(() => useFlushBeforeNav(), {
      wrapper: harness.wrapper,
    });
    await act(async () => {
      await result.current.navigate("/plasmodb/conversation/abc");
    });
    expect(pushMock).toHaveBeenCalledWith("/plasmodb/conversation/abc");
  });

  it("waits for an in-flight push to settle before navigating", async () => {
    const initial = makeStrategy();
    const harness = makeQueryHarness(initial);

    let resolveFn!: (s: Strategy) => void;
    pushConversationMock.mockReturnValueOnce(
      new Promise<Strategy>((resolve) => {
        resolveFn = resolve;
      }),
    );

    const { result } = renderHook(
      () => {
        const flush = useFlushBeforeNav();
        const push = usePushStrategyMutation();
        return { flush, push };
      },
      { wrapper: harness.wrapper },
    );

    act(() => {
      void result.current.push.mutateAsync({ optimistic: initial });
    });
    await waitFor(() => expect(result.current.flush.pending).toBe(true));

    let navResolved = false;
    let navPromise: Promise<void> = Promise.resolve();
    await act(async () => {
      navPromise = (async () => {
        await result.current.flush.navigate("/plasmodb/conversation/other");
        navResolved = true;
      })();
      await new Promise((r) => setTimeout(r, 10));
    });
    expect(navResolved).toBe(false);
    expect(pushMock).not.toHaveBeenCalled();

    await act(async () => {
      resolveFn(initial);
      await navPromise;
    });
    expect(navResolved).toBe(true);
    expect(pushMock).toHaveBeenCalledWith("/plasmodb/conversation/other");
  });
});

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

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), warning: vi.fn(), success: vi.fn() },
}));

import { useStrategyStore } from "@/state/strategy/store";
import { useStrategyAutoFlush } from "./useStrategyAutoFlush";
import { usePushStrategyMutation } from "@/features/strategy/mutations/usePushStrategyMutation";
import { makeQueryHarness } from "@/features/strategy/mutations/__tests__/strategyTestUtils";

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
  useStrategyStore.getState().clear();
  useStrategyStore.setState({ graphValidationStatus: {} });
  pushConversationMock.mockReset();
});

describe("useStrategyAutoFlush", () => {
  it("awaitFlush resolves immediately when no mutations are in flight", async () => {
    const harness = makeQueryHarness();
    const { result } = renderHook(() => useStrategyAutoFlush(), {
      wrapper: harness.wrapper,
    });
    await act(async () => {
      await result.current.awaitFlush();
    });
    expect(result.current.pending).toBe(false);
  });

  it("awaitFlush waits for an in-flight push to settle", async () => {
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
        const flush = useStrategyAutoFlush();
        const push = usePushStrategyMutation();
        return { flush, push };
      },
      { wrapper: harness.wrapper },
    );

    act(() => {
      void result.current.push.mutateAsync({ optimistic: initial });
    });
    await waitFor(() => expect(result.current.flush.pending).toBe(true));

    let flushResolved = false;
    let flushPromise: Promise<void> = Promise.resolve();
    await act(async () => {
      flushPromise = (async () => {
        await result.current.flush.awaitFlush();
        flushResolved = true;
      })();
      await new Promise((r) => setTimeout(r, 10));
    });
    expect(flushResolved).toBe(false);

    await act(async () => {
      resolveFn(initial);
      await flushPromise;
    });
    expect(flushResolved).toBe(true);
    await waitFor(() => expect(result.current.flush.pending).toBe(false));
  });
});

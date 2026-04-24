/**
 * @vitest-environment jsdom
 */

import type * as ConversationsModule from "@/lib/api/conversations";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { Strategy, Step } from "@pathfinder/shared";

const pushConversationMock = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api/conversations", async (importOriginal) => {
  const actual =
    await importOriginal<typeof ConversationsModule>();
  return { ...actual, pushConversation: pushConversationMock };
});

const toastErrorMock = vi.hoisted(() => vi.fn());
vi.mock("sonner", () => ({
  toast: { error: toastErrorMock, warning: vi.fn(), success: vi.fn() },
}));

import { useStrategyStore } from "@/state/strategy/store";
import { useDeleteStepMutation } from "./useDeleteStepMutation";
import { makeQueryHarness } from "./__tests__/strategyTestUtils";

function step(partial: Partial<Step> & { id: string; displayName: string }): Step {
  return { isBuilt: false, isFiltered: false, ...partial } as Step;
}

function makeStrategy(steps: Step[]): Strategy {
  return {
    id: "strategy-1",
    name: "Test",
    siteId: "plasmodb",
    recordType: "gene",
    steps,
    rootStepId: steps[steps.length - 1]?.id ?? null,
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

describe("useDeleteStepMutation", () => {
  it("removes the step from cache on mutate", async () => {
    const strategy = makeStrategy([
      step({ id: "s1", displayName: "S1", searchName: "geneById", recordType: "gene" }),
      step({ id: "s2", displayName: "S2", searchName: "geneById", recordType: "gene" }),
    ]);
    const harness = makeQueryHarness(strategy);
    pushConversationMock.mockResolvedValueOnce({
      ...strategy,
      steps: [strategy.steps[1]!],
      rootStepId: "s2",
    });

    const { result } = renderHook(
      () => useDeleteStepMutation(strategy.id),
      { wrapper: harness.wrapper },
    );

    let p: Promise<unknown> | undefined;
    act(() => {
      p = result.current.mutateAsync({ stepId: "s1" });
    });
    expect(harness.getStrategy(strategy.id)?.steps).toHaveLength(1);
    expect(harness.getStrategy(strategy.id)?.steps[0]?.id).toBe("s2");
    await act(async () => {
      await p;
    });
  });

  it("re-adds step on error", async () => {
    const strategy = makeStrategy([
      step({ id: "s1", displayName: "S1", searchName: "geneById", recordType: "gene" }),
      step({ id: "s2", displayName: "S2", searchName: "geneById", recordType: "gene" }),
    ]);
    const harness = makeQueryHarness(strategy);
    pushConversationMock.mockRejectedValueOnce(new Error("boom"));

    const { result } = renderHook(
      () => useDeleteStepMutation(strategy.id),
      { wrapper: harness.wrapper },
    );

    await act(async () => {
      await expect(
        result.current.mutateAsync({ stepId: "s1" }),
      ).rejects.toThrow("boom");
    });
    await waitFor(() => {
      expect(harness.getStrategy(strategy.id)?.steps).toHaveLength(2);
      const ids = harness
        .getStrategy(strategy.id)
        ?.steps.map((s) => s.id)
        .sort();
      expect(ids).toEqual(["s1", "s2"]);
    });
  });

  it("cascades to dependent steps (combine downstream of removed primary)", async () => {
    const strategy = makeStrategy([
      step({ id: "s1", displayName: "S1", searchName: "geneById", recordType: "gene" }),
      step({ id: "s2", displayName: "S2", searchName: "geneById", recordType: "gene" }),
      step({
        id: "c1",
        displayName: "Combine",
        primaryInputStepId: "s1",
        secondaryInputStepId: "s2",
        operator: "INTERSECT",
        recordType: "gene",
      }),
    ]);
    const harness = makeQueryHarness(strategy);

    pushConversationMock.mockImplementationOnce((_id, args) => {
      expect(args.strategyAst.root.id).toBe("s2");
      return Promise.resolve({
        ...strategy,
        steps: [strategy.steps[1]!],
        rootStepId: "s2",
      });
    });

    const { result } = renderHook(
      () => useDeleteStepMutation(strategy.id),
      { wrapper: harness.wrapper },
    );

    let p: Promise<unknown> | undefined;
    act(() => {
      p = result.current.mutateAsync({ stepId: "s1" });
    });
    const optimisticIds = harness
      .getStrategy(strategy.id)
      ?.steps.map((s) => s.id)
      .sort();
    expect(optimisticIds).toEqual(["s2"]);
    await act(async () => {
      await p;
    });
    expect(pushConversationMock).toHaveBeenCalledTimes(1);
  });
});
